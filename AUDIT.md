# Methodology audit — problem / solution pairs

Started 2026-09-08. One line each way; the reasoning lives in TRANSFER.md.

| # | Problem | Solution |
|---|---------|----------|
| 1 | Alignment between the real capture and ours is counted in frames from power-on, and our boot length moves with the compiler (fat LTO), so a fixed "real X ↔ ours Y" pairing breaks on unrelated edits. A vblank wait at the end of setup does NOT fix this. | Have the ROM write a **"battle started" marker** to a known RAM address, and have the harness align both captures on that event instead of on a frame number. `mettaur`/`wave` already align on the enemy's own state changes; the marker makes it universal. |
| 2 | Checks isolate layers only coarsely — all backgrounds off or all objects off — so unrelated elements ride together in one number, and we don't know which BG layer the HUD, panels and gauge each live on. | Use `--only-bg <n>` (already in the harness, used zero times) to compare **one BG layer at a time**, and first map which layer each element is on. |
| 3 | `field` cannot compare beyond one frame because the enemy acts on an RNG the two sides don't share. | The enemy is an **object**; the panels, backdrop and HUD are backgrounds. Compare the BG layers only, and the static planes hold over long windows with the RNG-driven sprite absent. |
| 4 | `result`'s fixture begins after the window has already arrived (it moves only at frames 0–2), so the check is one still picture. | Generate an **earlier save state** with the harness's `--savestate`, so the slide-in is inside the capture. |

## Parked

- **Audio** — not ready to work on; dropped for now (2026-09-08). The `audio` check stays in the suite at its recorded number so it cannot silently regress, but no effort goes into it until this is lifted.
