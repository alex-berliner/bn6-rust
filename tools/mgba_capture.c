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

#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <mgba/core/log.h>
#include <mgba/internal/gba/input.h>
#include <mgba-util/common.h>

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

	for (int i = 0; i < count; ++i) {
		if (g_a_ticks > 0) {
			if (i >= g_a_start && i < g_a_start + g_a_ticks) {
				core->setKeys(core, 1 << GBA_KEY_A);
			} else {
				core->setKeys(core, 0);
			}
		}
		core->runFrame(core);
		if (write_frame(buf, stride)) {
			return 1;
		}
	}

	free(buf);
	core->deinit(core);
	fprintf(stderr, "wrote %d frames to %s\n", g_frame, outdir);
	return 0;
}
