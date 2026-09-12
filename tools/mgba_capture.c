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
 *   --only-bg <n>      leave exactly BG layer <n> on, everything else
 *                      (including OBJ and both windows) off.
 *   --only-bg-with-obj <n>  the same single-BG isolation as --only-bg, but
 *                      leaves OBJ (and WIN0/WIN1) alone instead of forcing
 *                      them off too -- for isolating a sprite (a cursor, an
 *                      enemy) against one BG layer at a time. Does not
 *                      change what --only-bg or --disable-obj do.
 *   --disable-obj      turn OBJ (sprites) off, leave every BG layer alone.
 *
 * Each frame is written to <outdir>/frame.####.rgb as raw 32-bit native GBA
 * pixels (240*160*4 bytes), which tools/mgba_frames.py decodes to PNG.
 *
 *   --dump-audio <dir>  after every frame, drain the core's final stereo
 *                       mix and write it as signed 16-bit interleaved PCM to
 *                       <dir>/frame.####.pcm (one file per frame, same
 *                       numbering as the video). No container, no resampling
 *                       of our own. Reads core->getAudioChannel(core, 0/1),
 *                       which is the post-mix left/right bus (PSG + both
 *                       DirectSound FIFOs already summed), not a per-voice
 *                       tap -- combine with --audio-channel to isolate one
 *                       source. THE RATE IS NOT WHAT mCore ADVERTISES: this
 *                       build's mAVStream.audioRateChanged callback (fed by
 *                       gba->audio.sampleInterval) reports 65536 Hz, but
 *                       counting actual samples drained per frame gives
 *                       ~96000 Hz, consistently, state-load or not -- a real
 *                       ~1.46x gap between the two, not measurement noise
 *                       (confirmed over 299 frames: 95998.3 Hz). Something
 *                       about libmgba 0.10.2's blip_t rate setup and the
 *                       sampleInterval scalar have drifted apart. So this
 *                       flag does not print "the" rate up front; it prints
 *                       both numbers after the run ("audio: wrote N samples
 *                       over M frames ... = R Hz measured; ...reported G
 *                       Hz -- do not trust that number") and the measured
 *                       one (R) is the one to believe -- divide a file's
 *                       byte count by 4 * R for its duration in seconds.
 *   --audio-channel <id>  solo channel <id> (repeatable to solo several),
 *                       muting every other PSG/FIFO channel via
 *                       core->enableAudioChannel. The id table (from
 *                       core->listAudioChannels: 0-3 are the four PSG
 *                       channels, 4-5 are DirectSound FIFOs A/B) is printed
 *                       to stderr whenever this or --dump-audio is used, so
 *                       the ids are legible without reading this comment.
 *   --poke-at <frame>:<addr>:<value>  (repeatable, max 32) AUDIT wave 3c
 *                       "encounter-roll" ticket: a 16-bit write applied
 *                       exactly ONCE, immediately before the named frame
 *                       index runs -- unlike --cheat (every frame from the
 *                       start) and --poke (once, at load, before frame 0).
 *                       For triggering a one-shot condition partway through
 *                       an otherwise-untouched run (e.g. forcing the
 *                       overworld encounter-roll accumulator open on just
 *                       one specific frame so real per-frame play runs
 *                       right up to it), so a swept N samples whatever game
 *                       state has actually evolved to by frame N rather than
 *                       repeating frame 0's forced condition on every frame.
 *   --watch-write <addr>[:<len>]  (repeatable, max 8 ranges, 64 bytes total)
 *                       libmgba debugger WRITE watchpoints. Every store to a
 *                       watched byte prints one line to stderr BEFORE the
 *                       store lands: frame, address, old->new value, the
 *                       writing instruction's address (r15 minus the ARM/Thumb
 *                       pipeline offset), raw r15 and LR. The emulator is
 *                       never paused and no emulated timing changes (the shims
 *                       delegate to the original memory functions; the frame
 *                       keeps running inside the same runFrame call), so a
 *                       capture with watchpoints armed is frame-identical to
 *                       one without. Ranges are expanded to byte-granule
 *                       watchpoints for maximum sensitivity (one line per
 *                       store, any store width).
 *   --watch <addr>:<len>:<file>  (repeatable) after EVERY rendered frame,
 *                       read <len> bytes at <addr> and append them to
 *                       <file>, so it ends up frames*<len> bytes long -- one
 *                       snapshot per frame, unlike --dump which reads once
 *                       at the very end. For following a value that changes
 *                       every frame (a battle-started marker, a frame
 *                       counter) well enough to align two captures on it
 *                       instead of on a hardcoded frame number.
 *   --diff-against <dir>:<lag>:<file>  "stream, don't store": instead of
 *                       writing this run's own frame.####.rgb files, diff
 *                       every rendered frame N against <dir>/frame.%05d.rgb
 *                       for frame N-lag as it is rendered, and append the
 *                       differing-pixel count (RGB only, one u32 per frame,
 *                       little-endian) to <file>. No frame files of this
 *                       run's own are written when this flag is given. A
 *                       frame whose N-lag reference does not exist on disk
 *                       records the sentinel 0xFFFFFFFF.
 *   --trace-pc <addr>  (repeatable, max 4) AUDIT wave 3c "zero-enemy"/
 *                       "inert-enemy" tickets: a coarse execution trace for
 *                       finding a gate the existing tools (a memory --watch,
 *                       a --dump) cannot see because it lives in a register
 *                       or a branch, not a value that sits in RAM long
 *                       enough to read. `--trace-steps N` (default 200000)
 *                       bounds it: at the START of every frame, the ARM core
 *                       is single-stepped (core->step) up to N instructions,
 *                       checking PC (cpu->gprs[15]) after each one against
 *                       every traced address (both raw and -4, for Thumb's
 *                       prefetch offset on gprs[15]) and printing to stderr
 *                       "TRACE frame=N step=S PC=0x%08x r0..r3=... r5=...
 *                       r6=... r7=... lr=..." on a hit -- one line per hit,
 *                       not deduped, so a loop that revisits the address
 *                       shows every pass -- then the frame is finished with
 *                       one normal core->runFrame() call and video frames
 *                       ARE still written (same write_frame() the untraced
 *                       path uses). FOUND THE HARD WAY: single-stepping a
 *                       WHOLE frame (gating on cpu->cycles vs
 *                       core->frameCycles()) does not work -- cpu->cycles is
 *                       not the simple monotonic counter it looks like (the
 *                       observed delta went negative), so that loop never
 *                       saw its target and free-ran past the point where raw
 *                       core->step() keeps mgba's BIOS HLE dispatch coherent
 *                       ("Bad BIOS Load32" / "Bad memory Load8" on stderr
 *                       past ~1.9M consecutive steps -- actual emulator-
 *                       state corruption, not just slowness). The bounded,
 *                       runFrame()-terminated design is what ships; single-
 *                       stepping is still orders of magnitude slower than
 *                       runFrame() alone, so this is for a short diagnostic
 *                       capture, never the full harness.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <errno.h>
#include <sys/stat.h>
#include <fcntl.h>

/* The installed libmgba.so was built with debugger support (it exports
 * CLIDebuggerCreate and friends), which is a struct mCore ABI switch: core.h
 * guards debuggerPlatform/attachDebugger/etc. behind USE_DEBUGGERS, and
 * listAudioChannels/enableAudioChannel sit right after that block. Compiling
 * this file without the macro leaves this translation unit's struct mCore
 * one exec vtable slot short from that point on, so those two calls silently
 * read whatever library-internal pointer actually lives at that offset
 * instead (observed: listAudioChannels returned a garbage count and a NULL
 * table, segfaulting on first use). Every field the existing flags use
 * (setVideoBuffer, setKeys, busRead/Write*, runFrame, ...) is declared
 * earlier in the struct and is unaffected either way. */
#define USE_DEBUGGERS 1

#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <mgba/core/log.h>
#include <mgba/core/serialize.h>
#include <mgba/core/blip_buf.h>
#include <mgba/internal/gba/input.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/video.h>
/* --watch-write: the real debugger platform (mDebuggerAttach +
 * platform->setWatchpoint WATCHPOINT_WRITE) and its ARM internals, for the
 * struct ARMDebugger layout (to reach the CPU at hit time) and
 * _ARMPCAddress/_ARMInstructionLength (the ARM/Thumb r15 pipeline-offset
 * helpers the hit line reports). USE_DEBUGGERS is already defined above --
 * struct mCore only has debuggerPlatform/attachDebugger behind it, and the
 * installed libmgba.so was built with debuggers on, so both sides agree. */
#include <mgba/debugger/debugger.h>
#include <mgba/internal/arm/debugger/debugger.h>
#include <mgba/internal/arm/isa-inlines.h>
#include <mgba-util/common.h>
#include <mgba-util/vfs.h>

/* GBA framebuffer size; color_t is 32-bit native unless COLOR_16_BIT is set. */
#define GW 240
#define GH 160

static int g_frame = 0;
static const char* g_outdir;

/* --watch-write: frame index the watchpoint hit hook reports (set every
 * iteration of the main loop before runFrame, so a hit inside frame N's
 * runFrame reports N). */
static int g_wp_frame = 0;
static struct mDebugger* g_wp_debugger = NULL;

/* Hold-A control. */
static int g_a_ticks = 0;
static int g_a_start = 60;

/* --dump-audio: an mAVStream whose only real job is to catch the resampled
 * output rate mgba settles on (audioRateChanged fires once, synchronously,
 * from inside core->setAVStream). The actual samples are not read through
 * this stream -- postAudioFrame/postAudioBuffer's per-sample/per-callback
 * timing is undocumented, whereas core->getAudioChannel(core, 0/1) hands
 * back the same underlying blip_t buffers directly, and draining those once
 * per runFrame() is simpler and exactly matches the video loop's cadence. */
static unsigned g_audio_rate = 0;
static void on_audio_rate_changed(struct mAVStream* stream, unsigned rate) {
	(void) stream;
	g_audio_rate = rate;
}
static struct mAVStream g_stream = { .audioRateChanged = on_audio_rate_changed };

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

/* --watch-write hit hook. The ARM memory shim calls mDebuggerEnter BEFORE
 * the watched store lands: info->oldValue is the pre-write memory at the
 * access address, info->newValue is what the store will write, info->address
 * is the accessed address. We only log and return; the emulator is never
 * paused, because nothing in this tool consults debugger->state -- the main
 * loop drives core->runFrame() directly (never mDebuggerRun*), so after the
 * shim returns, the store completes and the frame runs on untouched. The
 * only debugger-side side effect is ARMDebuggerEnter's
 * `cpu->nextEvent = cpu->cycles`, which forces one early event check: no
 * event can be due there (nextEvent was the earliest scheduled cycle), so
 * the check is a no-op and the schedule is unchanged -- the frame-identity
 * and --only wave checks in this ticket verify that empirically. */
static void wp_entered(struct mDebugger* debugger, enum mDebuggerEntryReason reason,
                       struct mDebuggerEntryInfo* info) {
	if (reason != DEBUGGER_ENTER_WATCHPOINT || !info) return;
	struct ARMDebugger* ad = (struct ARMDebugger*) debugger->platform;
	struct ARMCore* cpu = ad->cpu;
	uint32_t r15 = cpu->gprs[ARM_PC];
	/* The store has not landed yet, so r15 still holds the prefetch address
	 * (executing instruction + 2x its length). _ARMPCAddress() strips that
	 * ARM/Thumb pipeline offset to the writing instruction's own address. */
	fprintf(stderr,
	        "WP frame=%d addr=0x%08X write old=0x%08X new=0x%08X at=0x%08X (%s) "
	        "r15=0x%08X lr=0x%08X\n",
	        g_wp_frame, info->address, info->type.wp.oldValue, info->type.wp.newValue,
	        _ARMPCAddress(cpu), cpu->cpsr.t ? "thumb" : "arm", r15,
	        cpu->gprs[ARM_LR]);
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

	/* Disable the battle field/background layers directly on the renderer so a
	 * whole-frame diff against the Rust version's plain background is possible.
	 * `--disable-bg` sets disableBG[0..3]=true (BG tiles hold the field/panel
	 * grid and the backdrop) and keeps disableOBJ=false so MegaMan + the attack
	 * (OBJ sprites) still render. The public enableVideoLayer segfaults for
	 * BG1-3 on libmgba 0.10.x, so we set the flags ourselves via the renderer
	 * reached through the GBA core (core->cpu->master is &gba->d). */
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--disable-bg") == 0) {
			struct ARMCore* cpu = (struct ARMCore*) core->cpu;
			struct GBA* gba = (struct GBA*) cpu->master;
			if (gba && gba->video.renderer) {
				for (int b = 0; b < 4; ++b)
					gba->video.renderer->disableBG[b] = true;
				gba->video.renderer->disableOBJ = false;
				gba->video.renderer->disableWIN[0] = true;
				gba->video.renderer->disableWIN[1] = true;
				fprintf(stderr, "disabled BG layers (field/background) on renderer\n");
			} else {
				fprintf(stderr, "could not reach GBA renderer for --disable-bg\n");
			}
		}
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
	/* `--poke-at frame:addr:value` (repeatable, max 32): the SAME 16-bit
	 * write as --poke, but applied exactly ONCE, immediately before the
	 * named frame index runs, instead of at load and instead of every frame
	 * (--cheat). AUDIT wave 3c "encounter-roll" ticket step 1: a per-frame
	 * --cheat that forces the encounter-roll accumulator
	 * (0x02001c16/0x02001c18) EVERY frame makes sub_80AA4C0's own GetRNG
	 * draw (traced live to ROM 0x080AA51E, its masked value/threshold
	 * compare completing by 0x080AA52A -- see the ticket report) behave as
	 * if frozen: the roll either succeeds on the very first frame it is
	 * evaluated or, if that first draw loses, keeps losing every frame after
	 * (nothing else appears to perturb GetRNG's state on this code path
	 * between successive per-frame draws when the accumulator itself is
	 * pinned open every frame) -- which is TRANSFER 7aw's own
	 * held-direction orbit trap, just walked through the accumulator cheat
	 * instead of through input. A one-shot poke lets the frame count leading
	 * up to it run untouched (real per-frame movement, real intervening
	 * GetRNG consumers), so the roll this triggers samples whatever GetRNG
	 * has actually reached BY frame N, not frame 0's fixed value -- sweeping
	 * N across separate captures samples a different draw each time instead
	 * of repeating the same one. */
	struct { int frame; uint32_t addr; uint16_t val; } poke_ats[32];
	int npoke_at = 0;
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--poke-at") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* c1 = strchr(p, ':');
			char* c2 = c1 ? strchr(c1 + 1, ':') : NULL;
			if (!c1 || !c2) {
				fprintf(stderr, "--poke-at: expected frame:addr:value, got '%s'\n", argv[i + 1]);
				return 1;
			}
			*c1 = 0; *c2 = 0;
			if (npoke_at >= 32) {
				fprintf(stderr, "--poke-at: too many (max 32)\n");
				return 1;
			}
			poke_ats[npoke_at].frame = atoi(p);
			poke_ats[npoke_at].addr = (uint32_t) strtoul(c1 + 1, NULL, 0);
			poke_ats[npoke_at].val = (uint16_t) strtoul(c2 + 1, NULL, 0);
			++npoke_at;
			free(p);
			++i;
		}
	}

	/* `--disable-obj` turns the sprites off and leaves the BG layers on, and
	 * `--only-bg <n>` leaves exactly one BG layer on and turns everything else
	 * (OBJ included) off. Both are for tile parity: with the objects gone, a
	 * whole-frame diff is a diff of the tilemaps alone, and one layer at a
	 * time says which layer a difference is in.
	 *
	 * `--only-bg-with-obj <n>` (AUDIT wave 3b ticket step 3): the SAME single
	 * -BG-layer isolation as `--only-bg`, but leaves OBJ (and WIN0/WIN1) alone
	 * instead of forcing them off -- for isolating a sprite (a cursor, a
	 * scrolling wave enemy) against exactly one BG layer at a time, which
	 * neither existing flag can do (`--only-bg` always drops OBJ with it,
	 * `--disable-obj` never isolates to one BG). A separate flag rather than
	 * a new argument shape for `--only-bg`, so every existing caller of
	 * `--only-bg` or `--disable-obj` is completely unaffected -- same flags,
	 * same behaviour, same output for the same input. */
	for (int i = 4; i < argc; ++i) {
		int only = -1;
		bool keep_obj = false;
		if (strcmp(argv[i], "--only-bg") == 0 && i + 1 < argc) {
			only = atoi(argv[i + 1]);
		} else if (strcmp(argv[i], "--only-bg-with-obj") == 0 && i + 1 < argc) {
			only = atoi(argv[i + 1]);
			keep_obj = true;
		} else if (strcmp(argv[i], "--disable-obj") != 0) {
			continue;
		}
		struct ARMCore* cpu = (struct ARMCore*) core->cpu;
		struct GBA* gba = (struct GBA*) cpu->master;
		if (!gba || !gba->video.renderer) {
			fprintf(stderr, "could not reach GBA renderer\n");
			continue;
		}
		gba->video.renderer->disableOBJ = !keep_obj;
		if (only >= 0) {
			for (int b = 0; b < 4; ++b)
				gba->video.renderer->disableBG[b] = (b != only);
			if (!keep_obj) {
				gba->video.renderer->disableWIN[0] = true;
				gba->video.renderer->disableWIN[1] = true;
			}
			fprintf(stderr, keep_obj ? "left only BG%d and OBJ on\n" : "left only BG%d on\n", only);
			++i;
		} else {
			fprintf(stderr, "disabled OBJ layer\n");
		}
	}

	/* Per-frame zero fills: `--zero addr:bytes` (decimal bytes), written
	 * before each frame like a cheat, for blanking sprite tiles the game
	 * uploads once (e.g. the ENEMY DELETED banner text in OBJ VRAM). */
	struct { uint32_t addr; int bytes; } zeros[16];
	int nzero = 0;
	for (int i = 4; i < argc; ++i) {
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
	/* Per-frame cheats: `--cheat addr:value`, re-written before each frame. */
	struct { uint32_t addr; uint16_t val; } cheats[64];
	int ncheat = 0;
	for (int i = 4; i < argc; ++i) {
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
	/* `--audio-channel <id>` (repeatable): solo the given channel(s), muting
	 * every other PSG/FIFO channel, via core->enableAudioChannel. This is an
	 * emulator-level force-mute (GBAAudio's forceDisableCh[]/forceDisableChA/
	 * B), not a RAM write, so unlike --cheat/--zero it only needs setting
	 * once, before the frame loop, not re-applied every frame. */
	int solo_ids[16];
	int nsolo = 0;
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--audio-channel") == 0 && i + 1 < argc) {
			if (nsolo < 16) solo_ids[nsolo++] = atoi(argv[i + 1]);
			++i;
		}
	}
	/* `--dump-audio <dir>`: see the header comment. Set up here, before the
	 * loop, so the stream is installed and any boot-time backlog in the
	 * blip buffers is drained before frame 0's dump. */
	const char* dumpaudio_dir = NULL;
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--dump-audio") == 0 && i + 1 < argc) {
			dumpaudio_dir = argv[i + 1];
			++i;
		}
	}
	struct blip_t* audio_left = NULL;
	struct blip_t* audio_right = NULL;
	long audio_samples_written = 0;
	if (dumpaudio_dir) {
		if (mkdir(dumpaudio_dir, 0755) != 0 && errno != EEXIST) {
			fprintf(stderr, "mkdir %s: %s\n", dumpaudio_dir, strerror(errno));
			return 1;
		}
		/* Installed purely for the header comment's honesty check below --
		 * do not trust this number on its own, see there. */
		core->setAVStream(core, &g_stream);
		audio_left = core->getAudioChannel(core, 0);
		audio_right = core->getAudioChannel(core, 1);
		/* Discard whatever boot/state-load already queued so frame 0's file
		 * holds only audio generated during frame 0 itself. */
		int16_t discard[4096];
		int avail = blip_samples_avail(audio_left);
		while (avail > 0) {
			int n = avail > 4096 ? 4096 : avail;
			blip_read_samples(audio_left, discard, n, 0);
			blip_read_samples(audio_right, discard, n, 0);
			avail = blip_samples_avail(audio_left);
		}
	}
	if (nsolo > 0 || dumpaudio_dir) {
		const struct mCoreChannelInfo* chaninfo = NULL;
		size_t nchan = core->listAudioChannels(core, &chaninfo);
		fprintf(stderr, "audio channels:\n");
		for (size_t c = 0; c < nchan; ++c) {
			fprintf(stderr, "  %zu: %s (%s)\n", chaninfo[c].id, chaninfo[c].visibleName,
			        chaninfo[c].visibleType ? chaninfo[c].visibleType : chaninfo[c].internalName);
		}
		if (nsolo > 0) {
			for (size_t c = 0; c < nchan; ++c) {
				bool keep = false;
				for (int s = 0; s < nsolo; ++s) {
					if (solo_ids[s] == (int) chaninfo[c].id) keep = true;
				}
				core->enableAudioChannel(core, chaninfo[c].id, keep);
			}
			fprintf(stderr, "soloed %d channel(s)\n", nsolo);
		}
	}

	/* `--watch addr:len:file` (repeatable): after EVERY rendered frame, read
	 * `len` bytes at `addr` and append them to `file`, so the file ends up
	 * frames * len bytes long -- one snapshot per frame, growing as the
	 * capture runs, unlike --dump which reads once at the very end. This is
	 * the alignment primitive AUDIT pair 1 wants: the ROM writes a "battle
	 * started" marker (and a battle frame counter) to a fixed RAM address
	 * every frame, and the harness aligns both captures on the frame where
	 * the watched bytes cross that marker instead of on a hardcoded frame
	 * number. Base-0 strtoul throughout, same reasoning as --dump above:
	 * atoi() reads "0x..." as 0 without complaining, silently disagreeing
	 * with a hex address parsed by strtoul(...,0) elsewhere in the same
	 * flag -- a length of 0 is refused rather than watching nothing. */
	struct { uint32_t addr; int len; FILE* f; } watches[16];
	int nwatch = 0;
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--watch") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* c1 = strchr(p, ':');
			char* c2 = c1 ? strchr(c1 + 1, ':') : NULL;
			if (!c1 || !c2) {
				fprintf(stderr, "--watch: expected addr:len:file, got '%s'\n", argv[i + 1]);
				return 1;
			}
			*c1 = 0; *c2 = 0;
			uint32_t addr = (uint32_t) strtoul(p, NULL, 0);
			int len = (int) strtoul(c1 + 1, NULL, 0);
			const char* path = c2 + 1;
			if (len <= 0) {
				fprintf(stderr, "--watch: byte count '%s' is not a positive "
				        "number (hex needs an 0x prefix)\n", c1 + 1);
				return 1;
			}
			if (nwatch >= 16) {
				fprintf(stderr, "--watch: too many watches (max 16)\n");
				return 1;
			}
			FILE* f = fopen(path, "wb");
			if (!f) {
				fprintf(stderr, "fopen %s: %s\n", path, strerror(errno));
				return 1;
			}
			watches[nwatch].addr = addr;
			watches[nwatch].len = len;
			watches[nwatch].f = f;
			++nwatch;
			fprintf(stderr, "watching %d bytes @ 0x%08x -> %s\n", len, addr, path);
			free(p);
			++i;
		}
	}

	/* `--watch-write addr[:len]` (repeatable, max 8 ranges, 64 bytes total):
	 * libmgba debugger WRITE watchpoints, not polling. Every store to a
	 * watched byte prints one line (see wp_entered above) with the frame,
	 * address, old->new value and the writing instruction's ROM address
	 * (r15 minus the ARM/Thumb pipeline offset), plus raw r15 and LR, so a
	 * clearing instruction can be attributed and then walked up the call
	 * chain via its LR. Design notes that make this safe to leave on for a
	 * whole capture:
	 *  - The watchpoints are the real debugger platform's shims
	 *    (memory-debugger.c): every shim delegates to the ORIGINAL memory
	 *    function with the same arguments and cycle counter, so no emulated
	 *    timing changes; only wall time grows.
	 *  - The emulator is never paused: the shim calls mDebuggerEnter, which
	 *    calls ARMDebuggerEnter (one no-op early event check) and then our
	 *    wp_entered hook, and returns. Nothing here reads debugger->state or
	 *    calls mDebuggerRun*, so execution continues inside the same
	 *    core->runFrame() call. Frame-identity with the flag off is checked
	 *    in this ticket's report.
	 *  - Each requested range is expanded to BYTE-granule watchpoints.
	 *    _checkWatchpoints matches `(watchpoint->address ^ address) &
	 *    ~(accessWidth-1)`, so a byte watch fires for ANY store width whose
	 *    access address lies in that byte's width-alignment window (a str at
	 *    0x02001b9c matches a byte watch at 0x02001b9d), and the shim stops
	 *    at the first matching watchpoint -- one line per store, at the
	 *    highest possible sensitivity (a word watch would miss byte stores
	 *    inside the word, and vice versa).
	 *  - Known-write anchor (R3): the encounter roll's
	 *    `str r0,[r7,#oGameState_CurBattleDataPtr]` (asm29.s:10286,
	 *    locGotBattleSettings_80AA59E, Thumb) must report
	 *    `at=0x080AA59E` when it writes 0x02001b9c. */
	struct { uint32_t addr; uint32_t len; } wp_ranges[8];
	int nwp_range = 0;
	int wp_total = 0;
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--watch-write") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* colon = strchr(p, ':');
			if (colon) *colon = 0;
			uint32_t addr = (uint32_t) strtoul(p, NULL, 0);
			uint32_t len = colon ? (uint32_t) strtoul(colon + 1, NULL, 0) : 4;
			free(p);
			if (!len) {
				fprintf(stderr, "--watch-write: length must be positive (hex needs an 0x prefix)\n");
				return 1;
			}
			if (nwp_range >= 8) {
				fprintf(stderr, "--watch-write: too many ranges (max 8)\n");
				return 1;
			}
			wp_total += len;
			if (wp_total > 64) {
				fprintf(stderr, "--watch-write: too many watched bytes (max 64 total)\n");
				return 1;
			}
			wp_ranges[nwp_range].addr = addr;
			wp_ranges[nwp_range].len = len;
			++nwp_range;
			++i;
		}
	}
	if (nwp_range > 0) {
		/* mDebuggerCreate returns NULL for DEBUGGER_CUSTOM (it only builds CLI
		 * and GDB debuggers), so build the struct mDebugger ourselves: set the
		 * entered hook, then mDebuggerAttach wires up the core's debugger
		 * platform (ARMDebuggerPlatformCreate), assigns us to
		 * CPU_COMPONENT_DEBUGGER and hotplug-inits it -- which snapshots the
		 * real memory function table the shims delegate to. Byte-granule
		 * WATCHPOINT_WRITEs go in after that. */
		g_wp_debugger = calloc(1, sizeof(struct mDebugger));
		if (!g_wp_debugger) {
			fprintf(stderr, "--watch-write: calloc failed\n");
			return 1;
		}
		g_wp_debugger->type = DEBUGGER_CUSTOM;
		g_wp_debugger->entered = wp_entered;
		mDebuggerAttach(g_wp_debugger, core);
		for (int r = 0; r < nwp_range; ++r) {
			for (uint32_t b = 0; b < wp_ranges[r].len; ++b) {
				struct mWatchpoint wp;
				memset(&wp, 0, sizeof(wp));
				wp.address = wp_ranges[r].addr + b;
				wp.segment = -1;
				wp.type = WATCHPOINT_WRITE;
				ssize_t id = g_wp_debugger->platform->setWatchpoint(g_wp_debugger->platform, &wp);
				if (id < 0) {
					fprintf(stderr, "--watch-write: setWatchpoint 0x%08X failed\n", wp_ranges[r].addr + b);
					return 1;
				}
			}
		}
		fprintf(stderr, "watch-write: %d range(s), %d byte watchpoint(s) armed\n", nwp_range, wp_total);
	}

	/* `--diff-against <dir>:<lag>:<file>`: "stream, don't store" (AUDIT pair
	 * 13 / Optimisations). Instead of writing this run's own frame.#####.rgb
	 * files, compare each rendered frame N directly against
	 * <dir>/frame.%05d.rgb for frame N-lag (a previously captured reference)
	 * and append the differing-pixel count for that frame, as a little-
	 * endian u32, to <file>. One record per rendered frame, in order, so
	 * <file> ends up exactly `count` u32s long -- a short file means a short
	 * capture, the same signal a normal run gives by writing fewer .rgb
	 * files (see tools/chip_compare.py's capture()). Comparison is RGB only
	 * (the 4th byte of each native pixel is unused, per mgba_frames.py's
	 * decode() comment), matching every other diff in the project. If frame
	 * N-lag does not exist on disk (e.g. N < lag), the record is the
	 * sentinel 0xFFFFFFFF rather than a bogus 0 or a crash. */
	const char* diffagainst_dir = NULL;
	long diffagainst_lag = 0;
	const char* diffagainst_file = NULL;
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--diff-against") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* c1 = strchr(p, ':');
			char* c2 = c1 ? strchr(c1 + 1, ':') : NULL;
			if (!c1 || !c2) {
				fprintf(stderr, "--diff-against: expected dir:lag:file, got '%s'\n", argv[i + 1]);
				return 1;
			}
			*c1 = 0; *c2 = 0;
			diffagainst_dir = strdup(p);
			diffagainst_lag = strtol(c1 + 1, NULL, 0);
			diffagainst_file = strdup(c2 + 1);
			free(p);
			++i;
		}
	}
	FILE* diffagainst_out = NULL;
	uint8_t* diffagainst_ref = NULL;
	const size_t diffagainst_framebytes = (size_t) GW * GH * sizeof(color_t);
	if (diffagainst_file) {
		diffagainst_out = fopen(diffagainst_file, "wb");
		if (!diffagainst_out) {
			fprintf(stderr, "fopen %s: %s\n", diffagainst_file, strerror(errno));
			return 1;
		}
		diffagainst_ref = malloc(diffagainst_framebytes);
		fprintf(stderr, "streaming diff against %s (lag %ld) -> %s; not writing frame files\n",
		        diffagainst_dir, diffagainst_lag, diffagainst_file);
	}

	/* `--trace-pc <addr>` (repeatable, max 4): see the header comment.
	 * `--trace-steps N` (default 200000) bounds how many instructions are
	 * single-stepped at the START of every traced frame before falling back
	 * to a normal core->runFrame() to finish it out. FOUND THE HARD WAY
	 * (this ticket): single-stepping a WHOLE frame's worth of cycles (the
	 * first version of this flag tried exactly that, gating on
	 * cpu->cycles vs core->frameCycles()) does not work -- cpu->cycles is
	 * not the simple monotonic counter it looks like from the struct
	 * definition (the observed delta went NEGATIVE), so the loop never sees
	 * its target and free-runs past the point where mgba's BIOS HLE
	 * dispatch stays coherent under raw core->step() -- "Bad BIOS Load32" /
	 * "Bad memory Load8" on stderr past ~1.9M consecutive steps in one
	 * frame, i.e. actual emulator-state corruption, not just slowness. A
	 * bounded step count well under that (200000 default, override with
	 * --trace-steps if a gate lives later in the frame than it can reach),
	 * followed by a normal runFrame() to reach the next vblank the safe
	 * way, stayed clean in testing and is what ships. */
	uint32_t trace_pcs[4];
	int ntrace = 0;
	long trace_steps = 200000;
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--trace-pc") == 0 && i + 1 < argc) {
			if (ntrace < 4) trace_pcs[ntrace++] = (uint32_t) strtoul(argv[i + 1], NULL, 0);
			++i;
		} else if (strcmp(argv[i], "--trace-steps") == 0 && i + 1 < argc) {
			trace_steps = strtol(argv[i + 1], NULL, 0);
			++i;
		}
	}
	if (ntrace > 0) {
		fprintf(stderr, "trace-pc: watching %d address(es), single-stepping the first %ld "
		        "instructions of every frame then finishing it with a normal runFrame() "
		        "(slow -- diagnostic use only)\n", ntrace, trace_steps);
		for (int t = 0; t < ntrace; ++t) fprintf(stderr, "  trace addr 0x%08x\n", trace_pcs[t]);
	}

	for (int i = 0; i < count; ++i) {
		/* --watch-write: the frame index the hit hook reports. */
		g_wp_frame = i;
		uint32_t keys = 0;
		if (g_a_ticks > 0 && i >= g_a_start && i < g_a_start + g_a_ticks) {
			keys |= 1 << GBA_KEY_A;
		}
		for (int t = 0; t < ntaps; ++t) {
			if (taps[t].frame == i) keys |= taps[t].key;
		}
		core->setKeys(core, keys);
		/* Per-frame "cheats": re-written before each frame so the game cannot
		 * overwrite them. Repeatable via --cheat addr:value. */
		for (int c = 0; c < ncheat; ++c) {
			core->busWrite16(core, cheats[c].addr, cheats[c].val);
		}
		for (int z = 0; z < nzero; ++z) {
			for (int b = 0; b < zeros[z].bytes; b += 2) {
				core->busWrite16(core, zeros[z].addr + b, 0);
			}
		}
		/* --poke-at: a ONE-SHOT write, the frame it names and no other. */
		for (int p = 0; p < npoke_at; ++p) {
			if (poke_ats[p].frame == i) {
				core->busWrite16(core, poke_ats[p].addr, poke_ats[p].val);
			}
		}
		if (ntrace > 0) {
			/* Single-step the first `trace_steps` instructions of this frame,
			 * checking PC against every traced address after each one, then
			 * hand off to a normal runFrame() to finish the frame out the
			 * proven-safe way. See the header comment by --trace-pc and the
			 * comment on trace_steps above for why it is bounded and why the
			 * frame is NOT single-stepped in full. */
			struct ARMCore* tcpu = (struct ARMCore*) core->cpu;
			for (long steps = 0; steps < trace_steps; ++steps) {
				core->step(core);
				uint32_t pc = (uint32_t) tcpu->gprs[15];
				for (int t = 0; t < ntrace; ++t) {
					/* Raw PC and PC-4: mgba's ARM_PC slot can read either the
					 * address of the instruction just executed or the
					 * prefetched next-but-one address depending on mode; a
					 * hit on either is reported so a Thumb branch target is
					 * not silently missed. */
					if (pc == trace_pcs[t] || pc - 4 == trace_pcs[t]) {
						fprintf(stderr,
						        "TRACE frame=%d step=%ld PC=0x%08x r0=0x%08x r1=0x%08x "
						        "r2=0x%08x r3=0x%08x r5=0x%08x r6=0x%08x r7=0x%08x lr=0x%08x\n",
						        i, steps, pc, tcpu->gprs[0], tcpu->gprs[1], tcpu->gprs[2],
						        tcpu->gprs[3], tcpu->gprs[5], tcpu->gprs[6], tcpu->gprs[7],
						        tcpu->gprs[14]);
					}
				}
			}
			core->runFrame(core);
		} else {
			core->runFrame(core);
		}
		if (dumpaudio_dir) {
			int avail = blip_samples_avail(audio_left);
			int availR = blip_samples_avail(audio_right);
			if (availR < avail) avail = availR;
			if (avail > 4096) avail = 4096;
			int16_t pcm[4096 * 2];
			if (avail > 0) {
				blip_read_samples(audio_left, pcm, avail, 1);
				blip_read_samples(audio_right, pcm + 1, avail, 1);
			}
			char pname[512];
			snprintf(pname, sizeof(pname), "%s/frame.%05d.pcm", dumpaudio_dir, i);
			FILE* pf = fopen(pname, "wb");
			if (!pf) {
				fprintf(stderr, "fopen %s: %s\n", pname, strerror(errno));
				return 1;
			}
			fwrite(pcm, sizeof(int16_t) * 2, avail, pf);
			fclose(pf);
			audio_samples_written += avail;
		}
		/* --watch: append this frame's snapshot of every watched range, after
		 * the frame has actually run. */
		for (int w = 0; w < nwatch; ++w) {
			for (int b = 0; b < watches[w].len; ++b) {
				uint8_t v = (uint8_t) core->busRead8(core, watches[w].addr + b);
				fwrite(&v, 1, 1, watches[w].f);
			}
		}
		if (diffagainst_file) {
			/* Streaming diff: no frame file of our own, just the count. */
			char rname[512];
			snprintf(rname, sizeof(rname), "%s/frame.%05ld.rgb", diffagainst_dir,
			         (long) i - diffagainst_lag);
			uint32_t ndiff = 0xFFFFFFFFu; /* sentinel: no reference frame */
			FILE* rf = fopen(rname, "rb");
			if (rf) {
				size_t got = fread(diffagainst_ref, 1, diffagainst_framebytes, rf);
				fclose(rf);
				if (got == diffagainst_framebytes) {
					ndiff = 0;
					const uint8_t* a = (const uint8_t*) buf;
					const uint8_t* b = diffagainst_ref;
					size_t npixels = (size_t) GW * GH;
					for (size_t px = 0; px < npixels; ++px) {
						size_t o = px * sizeof(color_t);
						/* RGB only -- the 4th byte is unused, same as every
						 * other diff in the project. */
						if (a[o] != b[o] || a[o + 1] != b[o + 1] || a[o + 2] != b[o + 2]) {
							++ndiff;
						}
					}
				}
			}
			fwrite(&ndiff, sizeof(ndiff), 1, diffagainst_out);
			++g_frame;
		} else if (write_frame(buf, stride)) {
			return 1;
		}
	}
	if (diffagainst_file) {
		fclose(diffagainst_out);
		free(diffagainst_ref);
		fprintf(stderr, "diff-against %s (lag %ld): wrote %d per-frame count(s) to %s\n",
		        diffagainst_dir, diffagainst_lag, g_frame, diffagainst_file);
	}
	for (int w = 0; w < nwatch; ++w) {
		fclose(watches[w].f);
		fprintf(stderr, "watch: wrote %d frame(s) x %d byte(s) @ 0x%08x\n",
		        g_frame, watches[w].len, watches[w].addr);
	}

	/* Dump a memory range to a file: `--dump addr:bytes:file`, taken AFTER the
	 * last frame runs, so `<count> N` dumps what memory holds once frame N-1
	 * has been drawn. It used to run before the loop, which silently made
	 * every dump a picture of the save state instead of of the frame being
	 * looked at. --peek still reads at load time. */
	for (int i = 4; i < argc; ++i) {
		if (strcmp(argv[i], "--dump") == 0 && i + 1 < argc) {
			char* p = strdup(argv[i + 1]);
			char* c1 = strchr(p, ':'); *c1 = 0; char* c2 = strchr(c1 + 1, ':');
			*c2 = 0;
			uint32_t addr = (uint32_t) strtoul(p, NULL, 0);
			/* Base 0 for the count as well as the address. It used to be
			 * atoi(), which returns 0 for "0x1c0" without complaining, so
			 * the two halves of one argument disagreed about their base
			 * and a hex count wrote an empty file and reported success.
			 * A count of 0 is now refused rather than dumping nothing. */
			int bytes = (int) strtoul(c1 + 1, NULL, 0);
			const char* path = c2 + 1;
			if (bytes <= 0) {
				fprintf(stderr, "--dump: byte count '%s' is not a positive "
				        "number (hex needs an 0x prefix)\n", c1 + 1);
				return 1;
			}
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

	if (dumpaudio_dir) {
		/* core->frequency()/frameCycles() give the emulated fps exactly
		 * (16777216 / 280896 = 59.7275...); dividing the actual sample
		 * count we wrote by the actual emulated seconds elapsed gives the
		 * PCM's true rate directly from the data, no library metadata
		 * required -- see the header comment for why that matters here. */
		double fps = (double) core->frequency(core) / core->frameCycles(core);
		double seconds = g_frame / fps;
		fprintf(stderr,
		        "audio: wrote %ld samples over %d frames (%.6f s) = %.1f Hz "
		        "measured; mAVStream.audioRateChanged reported %u Hz (do not "
		        "trust that number -- see header comment)\n",
		        audio_samples_written, g_frame, seconds,
		        seconds > 0 ? audio_samples_written / seconds : 0.0, g_audio_rate);
	}
	free(buf);
	core->deinit(core);
	fprintf(stderr, "wrote %d frames to %s\n", g_frame, outdir);
	return 0;
}
