# Fixture descriptor contract (AUDIT 6, 14, 17)

One ROM, any fixture. The harness writes a descriptor into EWRAM and the ROM reads it once at
startup. Written by the harness with per-frame `--cheat addr:val16` writes (or an `--init`
flag that does the same), so it is present whenever the ROM reads it and survives startup.

Address: **0x02000040** (the battle-started marker is at 0x02000000, 8 bytes). 64 bytes,
little-endian.

| off | type | field | meaning |
|-----|------|-------|---------|
| +0  | u32 | magic | `0x46495854` "FIXT". Absent → the ROM runs its normal full battle. |
| +4  | u8  | enemies | number of enemies, 0 = empty arena |
| +5  | u8  | enemy_kind | 0 = Mettaur (only kind for now) |
| +6  | u8  | enemy_col | panel column of the first enemy |
| +7  | u8  | enemy_row | panel row |
| +8  | u16 | megaman_hp | starting HP (canon captures use 60) |
| +10 | u8  | megaman_col | |
| +11 | u8  | megaman_row | |
| +12 | u8  | hand_count | 0..5 |
| +13 | u8[5] | hand | chip ids in the game's own numbering (`byte_2004C20` index) |
| +18 | u8  | gauge | 0 = empty, 1 = full |
| +19 | u8  | flags | bit0 open with the chip window; bit1 blank HUD; bit2 blank backdrop; bit3 auto-fire the hand; bit4 skip the white intro |
| +20 | u16 | art_entry | backdrop animation entry, 0xFFFF = default |
| +22 | u16 | art_timer | backdrop animation timer, 0xFFFF = default |
| +24 | u16 | scroll_xq | backdrop scroll, quarter-pixels, 0xFFFF = default |
| +26 | u16 | scroll_yq | |
| +28 | u16 | gauge_tick | gauge animation seed, 0xFFFF = default |
| +30 | u16 | fire_frame | battle frame on which auto-fire presses A (with bit3) |
| +32.. | | reserved | zero |

Every existing `demo-*` fixture must be expressible as one descriptor. The flags stay until
wave 3 confirms the new harness reproduces every check at zero through descriptors; then they go.
