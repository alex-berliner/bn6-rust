/*
 * Native frame capture via the mGBA core library.
 *
 * Instead of driving the mGBA Qt window on an X server and screen-scraping
 * (races, letterbox, menu-bar and window offsets), this links directly
 * against libmgba and runs the GBA core headlessly. It sets the core's
 * renderer output buffer to a buffer we own, advances the core one frame at a
 * time with core->runFrame, and saves the exact 240x160 GBA framebuffer once
 * per rendered frame -- in lock-step with the emulator, no X server at all.
 *
 * Usage:
 *   mgba_capture <rom.gba> <outdir> <count> [--press-A <ticks>]
 *
 *   <count>  number of emulated frames to step and dump.
 *   --press-A <ticks>  hold the A button down for <ticks> frames, starting at
 *                      frame 60. A debug or demo hand fires on A, so this
 *                      drives the attack without any window or key timers.
 *
 * Each frame is written to <outdir>/frame.####.rgb as raw 32-bit native GBA
 * pixels (240*160*4 bytes), which tools/mgba_frames.py decodes to PNG.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#include <fcntl.h>

#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <mgba/core/log.h>
#include <mgba/core/serialize.h>
#include <mgba/internal/gba/input.h>
#include <mgba-util/common.h>
#include <mgba-util/vfs.h>

/* GBA framebuffer size; color_t is 32-bit native unless COLOR_16_BIT is set. */
#define GW 240
#define GH 160

static int g_frame = 0;
static const char* g_outdir;

/* Hold-A control. */
static int g_a_ticks = 0;
static int g_a_start = 60;

static int write_frame(color_t* buf, size_t stride) {
	char name[512];
	snprintf(name, sizeof(name), "%s/frame.%05d.rgb", g_outdir, g_frame);
	FILE* f = fopen(name, "wb");
	if (!f) {
		fprintf(stderr, "fopen %s: %s\n", name, strerror(errno));
		return 1;
	}
	for (int y = 0; y < GH; ++y) {
		fwrite(buf + y * stride, sizeof(color_t), GW, f);
	}
	fclose(f);
	++g_frame;
	return 0;
}

int main(int argc, char** argv) {
	if (argc < 4) {
		fprintf(stderr,
		        "usage: %s <rom.gba> <outdir> <count> [--press-A <ticks>]\n",
		        argv[0]);
		return 2;
	}
	const char* rom = argv[1];
	const char* outdir = argv[2];
	g_outdir = outdir;
	int count = atoi(argv[3]);
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--press-A") == 0 && i + 1 < argc) {
			g_a_ticks = atoi(argv[i + 1]);
			++i;
		}
	}
	if (mkdir(outdir, 0755) != 0 && errno != EEXIST) {
		fprintf(stderr, "mkdir %s: %s\n", outdir, strerror(errno));
		return 1;
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
	mCoreInitConfig(core, "mgba_capture");
	/* Quiet the emulator: only fatal/error logs reach stderr, so the capture
	 * output is clean and the BIOS HLE chatter does not drown the run. */
	mCoreConfigSetIntValue(&core->config, "logLevel", mLOG_FATAL | mLOG_ERROR);

	/* This opens the ROM and calls the core's loadROM (gba/cor.c: the port's
	 * loadROM fills the cart and board). On failure it closes the VFile. */
	if (!mCoreLoadFile(core, rom)) {
		fprintf(stderr, "mCoreLoadFile %s failed\n", rom);
		return 1;
	}

	/* Own the framebuffer and install it before reset so the renderer is
	 * associated with it (GBACoreReset picks the renderer from outputBuffer). */
	size_t stride = GW;
	color_t* buf = calloc(GH * stride, sizeof(color_t));
	core->setVideoBuffer(core, buf, stride);

	core->reset(core);

	/* Load a battery save (Flash/SRAM .srm/.sav) if given, so the ROM boots
	 * into the saved game rather than the title. `--loadsave <file>`. */
	const char* savefile = NULL;
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--loadsave") == 0 && i + 1 < argc) {
			savefile = argv[i + 1];
			++i;
		}
	}
	if (savefile) {
		if (!mCoreLoadSaveFile(core, savefile, false)) {
			fprintf(stderr, "mCoreLoadSaveFile failed for %s\n", savefile);
			return 1;
		}
		fprintf(stderr, "loaded battery save %s\n", savefile);
		core->reset(core);
	}

	/* Load a save state (mGBA .ss<slot> file) if given, so a capture can start
	 * mid-battle instead of navigating the title/menu. `--loadstate <file>`. */
	const char* statefile = NULL;
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--loadstate") == 0 && i + 1 < argc) {
			statefile = argv[i + 1];
			++i;
		}
	}
	if (statefile) {
		/* mGBA-qt states are "RASTATE" (extdata banner) followed by the raw
		 * GBASerializedState; mCoreExtractState expects the raw state at
		 * offset 0. If the file begins with "RASTATE", re-emit a converted
		 * copy whose first bytes are the raw state, then load that. */
		FILE* sf = fopen(statefile, "rb");
		FILE* out = NULL;
		char convpath[512]; convpath[0] = 0;
		if (sf) {
			fseek(sf, 0, SEEK_END); long sz = ftell(sf); fseek(sf, 0, SEEK_SET);
			unsigned char* buf2 = malloc(sz);
			if (buf2 && fread(buf2, 1, sz, sf) == (size_t) sz && sz > 8 &&
			    memcmp(buf2, "RASTATE", 7) == 0) {
				/* Find the raw-state versionMagic (0x01000007). */
				int off = -1;
				for (int i = 0; i + 4 <= sz; ++i) {
					const unsigned char* p = buf2 + i;
					if (p[0] == 0x07 && p[1] == 0x00 && p[2] == 0x00 && p[3] == 0x01) {
						off = i; break;
					}
				}
				if (off > 0) {
					snprintf(convpath, sizeof(convpath), "%s.conv", statefile);
					out = fopen(convpath, "wb");
					if (out) {
						fwrite(buf2 + off, 1, sz - off, out);  /* raw state + rest */
						fclose(out); out = NULL;
						fprintf(stderr, "converted %s (core state at %d)\n", statefile, off);
					}
				}
			}
			free(buf2); fclose(sf);
		}
		const char* loadpath = convpath[0] ? convpath : statefile;
		struct VFile* svf = VFileOpen(loadpath, O_RDONLY);
		if (!svf) { fprintf(stderr, "cannot open state %s\n", loadpath); return 1; }
		if (!mCoreLoadStateNamed(core, svf, SAVESTATE_ALL)) {
			fprintf(stderr, "mCoreLoadStateNamed failed for %s\n", loadpath);
			if (convpath[0]) remove(convpath);
			return 1;
		}
		svf->close(svf);
		if (convpath[0]) remove(convpath);
		/* The state may have set its own keys/video; reinstall our buffer. */
		core->setVideoBuffer(core, buf, stride);
		fprintf(stderr, "loaded state %s\n", statefile);
	}

	/* A key script: "A@60" holds A for frame 60, "Start@120,A@130" etc. The
	 * game reads the pad each frame, so a one-frame tap is a press. */
	const char* script = NULL;
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--script") == 0 && i + 1 < argc) {
			script = argv[i + 1];
			++i;
		}
	}
	/* Parse the script up front into a small table. */
	struct Tap { int frame; uint32_t key; };
	struct Tap taps[1024];
	int ntaps = 0;
	if (script && *script) {
		char* s = strdup(script);
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
	}

	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--peek") == 0 && i + 1 < argc) {
			uint32_t addr = (uint32_t) strtoul(argv[i + 1], NULL, 0);
			uint16_t val = core->busRead16(core, addr);
			fprintf(stderr, "peek 0x%08x = 0x%04x\n", addr, val);
			++i;
		}
	}
	/* Dump a memory range to a file: `--dump addr:bytes:file`. Useful for
	 * reverse-engineering a struct (e.g. the live BattleState) without poking
	 * word by word. */
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--dump") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* c1 = strchr(p, ':'); *c1 = 0; char* c2 = strchr(c1 + 1, ':');
			*c2 = 0;
			uint32_t addr = (uint32_t) strtoul(p, NULL, 0);
			int bytes = atoi(c1 + 1);
			const char* path = c2 + 1;
			FILE* f = fopen(path, "wb");
			for (int b = 0; b < bytes; ++b) {
				uint8_t v = (uint8_t) core->busRead8(core, addr + b);
				fwrite(&v, 1, 1, f);
			}
			fclose(f);
			fprintf(stderr, "dumped %d bytes @ 0x%08x -> %s\n", bytes, addr, path);
			free(p); ++i;
		}
	}
	/* A memory poke after the state loads: `--poke addr:value` (16-bit value)
	 * writes to a 16-bit address, for patching battle RAM (e.g. the hand chip
	 * list at byte_20349C0). Repeatable. */
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--poke") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* colon = strchr(p, ':');
			if (colon) {
				*colon = 0;
				uint32_t addr = (uint32_t) strtoul(p, NULL, 0);
				uint16_t val = (uint16_t) strtoul(colon + 1, NULL, 0);
				core->busWrite16(core, addr, val);
				fprintf(stderr, "poke 0x%08x = 0x%04x\n", addr, val);
			}
			free(p);
			++i;
		}
	}

	for (int i = 0; i < count; ++i) {
		uint32_t keys = 0;
		if (g_a_ticks > 0 && i >= g_a_start && i < g_a_start + g_a_ticks) {
			keys |= 1 << GBA_KEY_A;
		}
		for (int t = 0; t < ntaps; ++t) {
			if (taps[t].frame == i) keys |= taps[t].key;
		}
		core->setKeys(core, keys);
		core->runFrame(core);
		if (write_frame(buf, stride)) {
			return 1;
		}
	}

	/* Optionally write a native savestate at the end (`--savestate <file>`),
	 * for round-tripping or producing a state another mGBA build can load. */
	const char* savestatefile = NULL;
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--savestate") == 0 && i + 1 < argc) {
			savestatefile = argv[i + 1];
			++i;
		}
	}
	if (savestatefile) {
		struct VFile* svf = VFileOpen(savestatefile, O_WRONLY | O_CREAT | O_TRUNC);
		if (!svf) { fprintf(stderr, "cannot open %s\n", savestatefile); return 1; }
		if (!mCoreSaveStateNamed(core, svf, SAVESTATE_ALL)) {
			fprintf(stderr, "mCoreSaveStateNamed failed for %s\n", savestatefile);
			return 1;
		}
		svf->close(svf);
		fprintf(stderr, "wrote state %s\n", savestatefile);
	}

	free(buf);
	core->deinit(core);
	fprintf(stderr, "wrote %d frames to %s\n", g_frame, outdir);
	return 0;
}
