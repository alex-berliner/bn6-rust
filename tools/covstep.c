/*
 * Instruction-coverage profiler for canon (T2 coverage ticket).
 *
 * Runs the real ROM headlessly under libmgba exactly the way
 * tools/mgba_capture.c drives it (same ROM/state/save/script/cheat/poke/
 * poke-at/zero semantics -- see the header comment there), but instead of
 * rendering frames it single-steps the ARM core and histograms every
 * executed PC per frame: for each distinct raw r15 value it records an
 * execution count and the first frame index that executed it, dumped to a
 * binary histogram at the end. tools/coverage.py maps PCs onto the
 * reference/bn6f disassembly's function symbols and writes the ranked
 * docs/coverage/<scenario>.md tables.
 *
 * Frame advance is by VCOUNT wrap (step until scanline counter leaves its
 * start value and comes back), NOT by runFrame: the point is to observe
 * every instruction of the frame, and runFrame would execute the bulk of
 * the frame unobserved. mgba_capture.c's --trace-pc comment records that
 * single-stepping whole frames via cpu->cycles gating corrupted emulator
 * state past ~1.9M consecutive steps; this tool gates on VCOUNT instead
 * (a memory-mapped counter, not cpu->cycles) and caps each frame at
 * COVSTEP_FRAME_CAP steps, printing a warning per frame that hits the cap
 * instead of silently free-running. No video frames are written.
 *
 * Usage:
 *   covstep <rom.gba> <count> --out <hist.bin>
 *     [--loadstate F] [--loadsave F] [--script "A@40,Start@10"]
 *     [--cheat addr:val16] [--poke addr:val16]
 *     [--poke-at frame:addr:val16] [--zero addr:len]
 *     [--dump addr:len:file] (repeatable, RAM snapshot at the end of the
 *     run -- for validating stepped emulation against runFrame captures)
 *
 * Histogram format (little-endian): u32 magic 0x43565331 ("CVS1"),
 * u32 nframes, u32 nentries, then nentries x (u32 raw_pc, u32 count,
 * u32 first_frame). raw_pc is ARMCore gprs[15] read immediately after the
 * step; coverage.py subtracts the Thumb pipeline offset (calibrated, see
 * its PC_ADJ comment) before attributing PCs to routines.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <errno.h>
#include <fcntl.h>

#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <mgba/core/log.h>
#include <mgba/core/serialize.h>
#include <mgba/internal/gba/input.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/video.h>
#include <mgba/internal/arm/debugger/debugger.h>
#include <mgba/internal/arm/isa-inlines.h>
#include <mgba-util/common.h>
#include <mgba-util/vfs.h>

#define GW 240
#define GH 160

/* Per-frame single-step guard: a GBA frame is 280636 cycles, so a few
 * hundred thousand instructions is the honest budget; 4M means the core is
 * stuck (halted CPU spinning on steps, or the VCOUNT read failing) and the
 * frame is abandoned with a warning rather than stepped forever. */
static const long COVSTEP_FRAME_CAP = 4000000L;  /* provenance: derived -- 280636 cycles/frame / 1 instr/cycle worst case, ~14x headroom */
static const uint32_t COVSTEP_VCOUNT = 0x04000006;  /* provenance: derived -- GBA MMIO VCOUNT register */

/* Open-addressing PC histogram: 2^20 slots, linear probing, key 0 = empty
 * (no emulated instruction ever executes at address 0 -- ROM/BIOS vectors
 * live at 0x08.../0x00... HLE'd natively, never stepped). */
#define HIST_BITS 20
#define HIST_SLOTS (1u << HIST_BITS)
static uint32_t* h_keys;
static uint32_t* h_counts;
static uint32_t* h_first;

static void hist_hit(uint32_t pc, uint32_t frame) {
	uint32_t slot = (pc * 2654435761u) >> (32 - HIST_BITS);
	while (h_keys[slot] != 0 && h_keys[slot] != pc) {
		slot = (slot + 1) & (HIST_SLOTS - 1);
	}
	if (h_keys[slot] == 0) {
		h_keys[slot] = pc;
		h_counts[slot] = 1;
		h_first[slot] = frame;
	} else {
		h_counts[slot]++;
	}
}

int main(int argc, char** argv) {
	if (argc < 3) {
		fprintf(stderr,
		        "usage: %s <rom.gba> <count> --out <hist.bin> [capture flags]\n",
		        argv[0]);
		return 2;
	}
	const char* rom = argv[1];
	int count = atoi(argv[2]);
	const char* outpath = NULL;
	for (int i = 3; i < argc; ++i) {
		if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) {
			outpath = argv[i + 1];
			++i;
		}
	}
	if (!outpath) {
		fprintf(stderr, "covstep: --out <hist.bin> is required\n");
		return 2;
	}

	struct mCore* core = mCoreCreate(mPLATFORM_GBA);
	if (!core) {
		fprintf(stderr, "mCoreCreate failed\n");
		return 1;
	}
	if (!core->init(core)) {
		fprintf(stderr, "core->init failed\n");
		return 1;
	}
	mCoreInitConfig(core, "covstep");
	mCoreConfigSetIntValue(&core->config, "logLevel", mLOG_FATAL | mLOG_ERROR);

	if (!mCoreLoadFile(core, rom)) {
		fprintf(stderr, "mCoreLoadFile %s failed\n", rom);
		return 1;
	}

	/* A video buffer is installed but never written to disk: the video
	 * emulation still renders into it while stepping, and a null renderer
	 * buffer is a segfault, not a saving. */
	size_t stride = GW;
	color_t* buf = calloc(GH * stride, sizeof(color_t));
	core->setVideoBuffer(core, buf, stride);

	core->reset(core);

	/* --loadsave (battery save), then reset: same order as mgba_capture.c. */
	for (int i = 3; i < argc; ++i) {
		if (strcmp(argv[i], "--loadsave") == 0 && i + 1 < argc) {
			if (!mCoreLoadSaveFile(core, argv[i + 1], false)) {
				fprintf(stderr, "mCoreLoadSaveFile failed for %s\n", argv[i + 1]);
				return 1;
			}
			fprintf(stderr, "loaded battery save %s\n", argv[i + 1]);
			core->reset(core);
			++i;
		}
	}

	/* --loadstate, with the same RASTATE conversion mgba_capture.c does. */
	for (int i = 3; i < argc; ++i) {
		if (strcmp(argv[i], "--loadstate") == 0 && i + 1 < argc) {
			const char* statefile = argv[i + 1];
			FILE* sf = fopen(statefile, "rb");
			char convpath[512]; convpath[0] = 0;
			if (sf) {
				fseek(sf, 0, SEEK_END); long sz = ftell(sf); fseek(sf, 0, SEEK_SET);
				unsigned char* buf2 = malloc(sz);
				if (buf2 && fread(buf2, 1, sz, sf) == (size_t) sz && sz > 8 &&
				    memcmp(buf2, "RASTATE", 7) == 0) {
					int off = -1;
					for (int j = 0; j + 4 <= sz; ++j) {
						const unsigned char* p = buf2 + j;
						if (p[0] == 0x07 && p[1] == 0x00 && p[2] == 0x00 && p[3] == 0x01) {
							off = j; break;
						}
					}
					if (off > 0) {
						snprintf(convpath, sizeof(convpath), "%s.conv", statefile);
						FILE* out = fopen(convpath, "wb");
						if (out) {
							fwrite(buf2 + off, 1, sz - off, out);
							fclose(out);
							fprintf(stderr, "converted %s (core state at %d)\n", statefile, off);
						} else {
							convpath[0] = 0;
						}
					}
				}
				free(buf2); fclose(sf);
			}
			const char* loadpath = convpath[0] ? convpath : statefile;
			struct VFile* svf = VFileOpen(loadpath, O_RDONLY);
			if (!svf) {
				fprintf(stderr, "cannot open state %s\n", loadpath);
				return 1;
			}
			if (!mCoreLoadStateNamed(core, svf, SAVESTATE_ALL)) {
				fprintf(stderr, "mCoreLoadStateNamed failed for %s\n", loadpath);
				if (convpath[0]) remove(convpath);
				return 1;
			}
			svf->close(svf);
			if (convpath[0]) remove(convpath);
			core->setVideoBuffer(core, buf, stride);
			fprintf(stderr, "loaded state %s\n", statefile);
			++i;
		}
	}

	/* --script: the same "Key@frame" tap syntax as mgba_capture.c
	 * (multi-frame holds are repeated taps from harness held()). */
	struct Tap { int frame; uint32_t key; };
	struct Tap taps[1024];
	int ntaps = 0;
	for (int i = 3; i < argc; ++i) {
		if (strcmp(argv[i], "--script") == 0 && i + 1 < argc) {
			char* s = strdup(argv[i + 1]);
			char* tok = strtok(s, ",");
			while (tok) {
				int frame = 0; const char* key = tok;
				char* at = strchr(tok, '@');
				if (at) { *at = 0; frame = atoi(at + 1); }
				uint32_t bits = 0;
				if      (!strcmp(key, "A")) bits = 1 << GBA_KEY_A;
				else if (!strcmp(key, "B")) bits = 1 << GBA_KEY_B;
				else if (!strcmp(key, "Select")) bits = 1 << GBA_KEY_SELECT;
				else if (!strcmp(key, "Start")) bits = 1 << GBA_KEY_START;
				else if (!strcmp(key, "Right")) bits = 1 << GBA_KEY_RIGHT;
				else if (!strcmp(key, "Left")) bits = 1 << GBA_KEY_LEFT;
				else if (!strcmp(key, "Up")) bits = 1 << GBA_KEY_UP;
				else if (!strcmp(key, "Down")) bits = 1 << GBA_KEY_DOWN;
				else if (!strcmp(key, "R")) bits = 1 << GBA_KEY_R;
				else if (!strcmp(key, "L")) bits = 1 << GBA_KEY_L;
				if (frame >= 0 && frame < count && ntaps < 1024) {
					taps[ntaps].frame = frame; taps[ntaps].key = bits; ++ntaps;
				}
				tok = strtok(NULL, ",");
			}
			free(s);
			++i;
		}
	}

	/* --poke (once, at load): same 16-bit write as mgba_capture.c. */
	for (int i = 3; i < argc; ++i) {
		if (strcmp(argv[i], "--poke") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* colon = strchr(p, ':');
			if (colon) {
				*colon = 0;
				core->busWrite16(core, (uint32_t) strtoul(p, NULL, 0),
				                 (uint16_t) strtoul(colon + 1, NULL, 0));
			}
			free(p);
			++i;
		}
	}

	/* --cheat (every frame) and --zero (every frame): parsed here, applied
	 * in the frame loop, same as mgba_capture.c. */
	struct { uint32_t addr; uint16_t val; } cheats[64];
	int ncheat = 0;
	for (int i = 3; i < argc; ++i) {
		if (strcmp(argv[i], "--cheat") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* colon = strchr(p, ':');
			if (colon && ncheat < 64) {
				*colon = 0;
				cheats[ncheat].addr = (uint32_t) strtoul(p, NULL, 0);
				cheats[ncheat].val = (uint16_t) strtoul(colon + 1, NULL, 0);
				++ncheat;
			}
			free(p);
			++i;
		}
	}
	struct { uint32_t addr; int bytes; } zeros[16];
	int nzero = 0;
	for (int i = 3; i < argc; ++i) {
		if (strcmp(argv[i], "--zero") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* colon = strchr(p, ':');
			if (colon && nzero < 16) {
				*colon = 0;
				zeros[nzero].addr = (uint32_t) strtoul(p, NULL, 0);
				zeros[nzero].bytes = atoi(colon + 1);
				++nzero;
			}
			free(p);
			++i;
		}
	}

	/* --poke-at (one-shot, before the named frame): same as mgba_capture.c. */
	struct { int frame; uint32_t addr; uint16_t val; } poke_ats[32];
	int npoke_at = 0;
	for (int i = 3; i < argc; ++i) {
		if (strcmp(argv[i], "--poke-at") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* c1 = strchr(p, ':');
			char* c2 = c1 ? strchr(c1 + 1, ':') : NULL;
			if (!c1 || !c2) {
				fprintf(stderr, "--poke-at: expected frame:addr:value, got '%s'\n", argv[i + 1]);
				return 1;
			}
			*c1 = 0; *c2 = 0;
			if (npoke_at < 32) {
				poke_ats[npoke_at].frame = atoi(p);
				poke_ats[npoke_at].addr = (uint32_t) strtoul(c1 + 1, NULL, 0);
				poke_ats[npoke_at].val = (uint16_t) strtoul(c2 + 1, NULL, 0);
				++npoke_at;
			}
			free(p);
			++i;
		}
	}

	h_keys = calloc(HIST_SLOTS, sizeof(uint32_t));
	h_counts = calloc(HIST_SLOTS, sizeof(uint32_t));
	h_first = calloc(HIST_SLOTS, sizeof(uint32_t));
	if (!h_keys || !h_counts || !h_first) {
		fprintf(stderr, "histogram alloc failed\n");
		return 1;
	}

	/* --dump addr:len:file (repeatable): a RAM snapshot at the END of the
	 * run, for validating stepped emulation against mgba_capture's
	 * runFrame-driven --dump of the same scenario and frame count. The
	 * stored path pointer aliases argv, which outlives the run. */
	struct { uint32_t addr; int len; const char* path; } dumps[8];
	int ndump = 0;
	for (int i = 3; i < argc; ++i) {
		if (strcmp(argv[i], "--dump") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* c1 = strchr(p, ':');
			char* c2 = c1 ? strchr(c1 + 1, ':') : NULL;
			if (!c1 || !c2) {
				fprintf(stderr, "--dump: expected addr:len:file, got '%s'\n", argv[i + 1]);
				return 1;
			}
			*c1 = 0; *c2 = 0;
			if (ndump < 8) {
				dumps[ndump].addr = (uint32_t) strtoul(p, NULL, 0);
				dumps[ndump].len = atoi(c1 + 1);
				dumps[ndump].path = argv[i + 1] + (c2 - p) + 1;
				++ndump;
			}
			free(p);
			++i;
		}
	}

	struct ARMCore* cpu = (struct ARMCore*) core->cpu;
	long total_steps = 0;
	int capped = 0;
	for (int i = 0; i < count; ++i) {
		uint32_t keys = 0;
		for (int t = 0; t < ntaps; ++t) {
			if (taps[t].frame == i) keys |= taps[t].key;
		}
		core->setKeys(core, keys);
		for (int c = 0; c < ncheat; ++c) {
			core->busWrite16(core, cheats[c].addr, cheats[c].val);
		}
		for (int z = 0; z < nzero; ++z) {
			for (int b = 0; b < zeros[z].bytes; b += 2) {
				core->busWrite16(core, zeros[z].addr + b, 0);
			}
		}
		for (int p = 0; p < npoke_at; ++p) {
			if (poke_ats[p].frame == i) {
				core->busWrite16(core, poke_ats[p].addr, poke_ats[p].val);
			}
		}
		/* One frame = one full VCOUNT cycle: step until the scanline
		 * counter leaves its start value and returns to it. */
		uint32_t v0 = core->busRead16(core, COVSTEP_VCOUNT);
		bool left = false;
		long steps = 0;
		for (;;) {
			core->step(core);
			hist_hit((uint32_t) cpu->gprs[15], (uint32_t) i);
			++steps;
			uint32_t v = core->busRead16(core, COVSTEP_VCOUNT);
			if (v != v0) left = true;
			else if (left) break;
			if (steps >= COVSTEP_FRAME_CAP) {
				fprintf(stderr, "covstep: frame %d hit the %ld-step cap -- "
				        "its tail is unobserved\n", i, COVSTEP_FRAME_CAP);
				++capped;
				break;
			}
		}
		total_steps += steps;
		if ((i & 63) == 63) {
			fprintf(stderr, "covstep: frame %d/%d (%ld steps this frame)\n",
			        i + 1, count, steps);
		}
	}
	fprintf(stderr, "covstep: %d frames, %ld steps total, %d capped frames\n",
	        count, total_steps, capped);

	uint32_t nentries = 0;
	for (uint32_t s = 0; s < HIST_SLOTS; ++s) {
		if (h_keys[s] != 0) ++nentries;
	}
	FILE* out = fopen(outpath, "wb");
	if (!out) {
		fprintf(stderr, "cannot open %s: %s\n", outpath, strerror(errno));
		return 1;
	}
	uint32_t magic = 0x31535643;  /* "CVS1" */
	uint32_t nf = (uint32_t) count;
	fwrite(&magic, 4, 1, out);
	fwrite(&nf, 4, 1, out);
	fwrite(&nentries, 4, 1, out);
	for (uint32_t s = 0; s < HIST_SLOTS; ++s) {
		if (h_keys[s] != 0) {
			fwrite(&h_keys[s], 4, 1, out);
			fwrite(&h_counts[s], 4, 1, out);
			fwrite(&h_first[s], 4, 1, out);
		}
	}
	fclose(out);
	fprintf(stderr, "covstep: wrote %u PCs to %s\n", nentries, outpath);
	for (int d = 0; d < ndump; ++d) {
		FILE* f = fopen(dumps[d].path, "wb");
		if (!f) {
			fprintf(stderr, "cannot open %s: %s\n", dumps[d].path, strerror(errno));
			return 1;
		}
		for (int b = 0; b < dumps[d].len; ++b) {
			uint8_t v = core->busRead8(core, dumps[d].addr + b);
			fwrite(&v, 1, 1, f);
		}
		fclose(f);
	}
	return 0;
}
