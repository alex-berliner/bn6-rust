# Port plan: the three battle interpreters (T3)

Source of truth: `docs/coverage/battle_full.md` (1140 routines, 318 in no
harness row) and `docs/coverage/mettaur.md` (517), both profiled with
`tools/covstep.c` against `reference/bn6f@d0952de8`. Every `file:line`
below was re-verified against the disassembly (the verifier checks the
symbols, so: label lines, not `thumb_func_start` lines).

Baseline (no `src/` change on this ticket; nothing to re-measure):
`battle_full` ranks quoted per routine are the before-state. The correction
in §1 (the coverage doc's "CANDIDATE" is not the player) is the main
finding; the plan ports the real player.

Note on "T1b": the ticket asks how "the trace harness (T1b)" verifies each
interpreter. There is no `T1b` in the tree — zero hits for `T1b` in `docs/`,
`tools/`, `src/`, `AGENTS.md`, `FIXTURE.md`. Verification below therefore
names the tooling that exists: `tools/probe.py` (`watch`/`peek` over
`mgba_capture`), `tools/oracle.py` (named PARITY fields), and the harness
rows (`python3 tools/harness.py --only ROW [--ui isolated]`).

---

## 1. Animation bytecode player (the `.spr`/`.anim` interpreter)

### 1.1 Entry routines (verified symbols)

Public ROM-side wrappers (`reference/bn6f/asm/sprite.s`) — all called
through `r5` = the `BattleObject`, offset by
`oObjectHeader_TypeAndSpriteOffset >> 4 << 4` to reach its `ObjectSprite`:

| symbol | file:line | ROM addr (decomp) | role |
| --- | --- | --- | --- |
| `sprite_loadAnimationData` | sprite.s:4 | `0x80026A4` (`docs/decomp/sprite.c:3`) | (re)bind anim `Unk_00` to its command stream |
| `sprite_loadAnimationData_spritePtrProvidedDirectly` | sprite.s:17 | `0x80026B6` | same, `r5` already the `ObjectSprite` (chatbox path) |
| `sprite_update` | sprite.s:28 | `0x80026C4` (`docs/decomp/sprite.c:23`) | advance one frame |
| `sprite_chatbox_80026D6` | sprite.s:41 | `0x80026D6` | same, direct pointer (chatbox path) |
| `sprite_setAnimation` | sprite.s:1131 | write `CurAnim` byte into the sprite state |
| `sprite_setAnimationAlt` | sprite.s:1120 | variant writer |
| `sprite_getFrameParameters` | sprite.s:1193 | reads current frame params (`src/spr.rs::on_last_frame` models its bit `0x80`; asm/sprite.s:1182-1198) |

IWRAM-resident cores (`reference/bn6f/asm/asm38.s`) — the wrappers load
their address (`off_80026C0` / `off_80026E0`) and reach them by `bx r4`,
never by `bl` (so a `bl` cross-reference search finds nothing; this is why
the coverage funcmap cannot pin them):

| symbol | file:line | role |
| --- | --- | --- |
| `_sprite_loadAnimationData` | asm38.s:1667 | bind: pick command stream for anim index |
| `_sprite_update` | asm38.s:1722 | tick: countdown, consume command bytes, emit frame key |

Per-frame gate (`reference/bn6f/asm/asm00_2.s`) — what battle objects
actually call each frame:

| symbol | file:line | role |
| --- | --- | --- |
| `object_updateSprite` | asm00_2.s:25045 | pause/flag/timestop gates, `CurAnim` vs `CurAnimCopy` rebind protocol, then `sprite_update` |
| `object_updateSpriteTimestop` | asm00_2.s:25084 | same minus the timestop gate (runs during timestop) |
| `sub_801BC24` | asm00_2.s:25110 | rebind-only variant (no `sprite_update` on the rebind path) |
| `UpdateBattleObjectSprite` | asm00_2.s:25144 | flag-checked wrapper (`ACTIVE`, `STOP_SPRITE_UPDATE`, `UPDATE_DURING_TIMESTOP`) dispatching to the above |

Correction to the coverage doc: `sub_80028C0` (sprite.s:359, rank 25
battle_full / 27 mettaur) is **not** the player. It is three instructions
— store one byte of `dword_200F340` into `byte_200F389[r0]` — i.e. OAM-slot
bookkeeping called from the object-iteration loop (`sub_8003BF4`,
`sub_8003C70`, asm00_1.s). The player entry itself stays symbol-pinned as
above; the *cores* are unpinnable-by-`bl` by construction (`bx r4`).

### 1.2 Bytecode format (read off `_sprite_loadAnimationData` + `_sprite_update`)

Per-sprite state is `ObjectSprite`
(`reference/bn6f/include/structs/ObjectSprite.inc`): `Unk_00` anim index,
`Unk_01` countdown, `Unk_02` next duration, `Unk_03` flags (`0x80` = alt
stream), `Unk_05` emitted frame key, `Unk_18` anim-table base, `Unk_1c`
alt-stream pointer, `Unk_20` command pointer.

- Bind (`_sprite_loadAnimationData`, asm38.s:1667): normal path
  (`Unk_03 & 0x80 == 0`) indexes a dword table at `[Unk_18]` by
  `Unk_00 * 4`, follows `+8` to the frame list, takes its first entry as
  `Unk_20`, and loads `Unk_01`/`Unk_02` from command bytes 1/2. Alt path
  (`Unk_03 & 0x80`) indexes `[Unk_18]` by `Unk_00 * 4` directly into
  `Unk_1c`, then `+8`/first-entry into `Unk_20`.
- Tick (`_sprite_update`, asm38.s:1722): decrement `Unk_01`; while
  negative, consume: normal stream reads `cmd[1]` (duration) / `cmd[2]`
  (next); `cmd[2] & 0x80` set ends the stream — `& 0x40` restarts it via
  `_sprite_loadAnimationData` (loop), otherwise `Unk_01 = 1` (hold last
  frame). Else `Unk_20 += 3` and reload durations. Alt stream advances
  `Unk_1c += 0x14` and re-resolves `Unk_20` through `[Unk_18] + [Unk_1c+8]`.
- Output (both paths' tail): `cmd[0] << 2` indexes a pointer table at
  `[Unk_1c + 0xC]` (resolved against `Unk_18`); the selected entry's word
  at `+4`, shifted right 4, is stored to `Unk_05` — the frame key the
  renderer consumes.

Our `assets/*.bin` (`BNSP`, written by `tools/spr_export.py`, inspected
with `tools/bnsview.py`) is this bytecode already flattened at export
time: anim table `(first frame, count)`, 10-byte frames
`(gfx, pal, oam_first, oam_count, duration, flags)` with `0x80` = last,
`0x40` = loop-after-last, and 6-byte OAM records. The exporter resolved
the `cmd → table → frame` indirection; the port must reproduce the
resolution, not the flat tables.

### 1.3 Callers (coverage tables + static sites)

- `battle_full`: no resolved row for `sprite_update`,
  `sprite_loadAnimationData`, `sprite_setAnimation`, `object_updateSprite`,
  `_sprite_update`, or `_sprite_loadAnimationData` — all are
  address-suffix-less entries (wrappers) or `bx`-only targets (cores), so
  their executed instructions attribute to neighbouring resolved symbols.
  The path IS hot: `sub_80028C0` rank 25 (2754 calls, frame 0),
  `sprite_chatbox_80026D6` rank 57 (1377 calls, frame 0),
  `sprite_resetObjVars_800289C` rank 152, `sprite_setAlpha_8002c7a`
  rank 537.
- `mettaur`: same shape (`sub_80028C0` rank 27, 1290 calls, frame 0).
- Static `bl` sites in `reference/bn6f/asm/` (exact-word counts):
  `sprite_update` 204, `sprite_loadAnimationData` 588,
  `sprite_setAnimation` 455, `object_updateSprite` 131 (all sampled sites
  in `asm31.s` per-type spawn/init paths, e.g. `:1071`, `:1125`, `:1519`),
  `object_updateSpriteTimestop` 75, `UpdateBattleObjectSprite` 12+
  (all in `asm31.s` per-type handler tails — the "fall through to the
  player" the ticket cites) plus `UpdateBattleObjectSpriteIfStatusPermits`
  sites. `battleObject_dispatch` itself never `bl`s the player; the
  per-type handlers do after dispatch returns.

### 1.4 Port order

1. `_sprite_loadAnimationData` (asm38.s:1667-1719): both bind paths;
   data read — the ROM sprite blob's anim/frame tables via `Unk_18`.
2. `_sprite_update` normal stream + `Unk_05` output (asm38.s:1722-1770):
   countdown/consume/loop-or-hold; data read — command bytes at `Unk_20`,
   pointer table at `[Unk_1c+0xC]`.
3. Alt stream (`Unk_03 & 0x80` branch) and `sprite_setAnimation` /
   `CurAnim`→`Unk_00` write path.
4. `object_updateSprite` gate + `CurAnim`/`CurAnimCopy` rebind protocol
   (asm00_2.s:25045-25100), then the timestop/`sub_801BC24`/
   `UpdateBattleObjectSprite` variants.

### 1.5 Trace verification (no T1b; probe + oracle + harness)

- Scenario: `mettaur` row (sterile ROM, `pausedwithcannon.state`,
  `Start@10`, ALIVE cheats `0x0203ab84:0xffff`/`0x0203ab86:0xffff`, 215
  frames) — the Mettaur breathes idle, so the player ticks without attack
  noise; plus `battle_full` (530 frames from `overworld_net.state`) for
  spawn-path rebinds.
- Fields: `probe.py watch <rom> <frames> 0x0203a9c0:2 0x0203ab70:2`
  (MegaMan `BattleObject+0x10` `CurAnim`/`CurAnimCopy`, enemy slot
  `0x0203ab60+0x10`; offsets per
  `reference/bn6f/include/structs/BattleObject.inc:56-59`) — expect
  `CurAnimCopy` to follow `CurAnim` exactly one `object_updateSprite`
  later, and `CurAnim` to step only when canon's AI writes it. Oracle
  PARITY fields `mm_anim` / `enemy_anim` (identity: our anim indices ARE
  canon's table indices) on the same rows compare frame-by-frame already.
- What it replaces: `src/spr.rs::Player` (`new`/`play`/`update`/
  `load_frame`, the `fresh`-frame semantics, `finished`/`on_last_frame`,
  palette-add/offset/white/red handling) — the Player becomes a thin shell
  over the ported tick/bind fed by BNSP tables kept in ROM layout.

### 1.6 Port log (T4, steps 1-2 landed)

- `src/spr.rs::Player` now carries the ROM state (`anim` = `Unk_00`,
  `countdown` = `Unk_01`, `cmd_flags` = `Unk_02`, `unk05` = `Unk_05`) with
  `bind()` = `_sprite_loadAnimationData` normal path (asm38.s:1667-1719)
  and `update()` = `_sprite_update` normal stream + `Unk_05` tail
  (asm38.s:1722-1790), over the BNSP tables (`duration` = command byte 1,
  `flags` = command byte 2 with `0x80` end / `0x40` loop; the exporter's
  frame-select pre-resolves `cmd[0]`; `Unk_05` = first OAM entry's palette
  bank, exposed via `unk05()` for the trace tooling). The hold state keeps
  a `done` latch for `finished()` instead of re-consuming the end marker
  (display-identical). Alt stream and `sprite_setAnimation`/`CurAnim` path
  stay T4b. No `src/anim.rs`: the port lives behind `Player`'s existing
  interface. No `tools/trace.py` exists, so no trace changes.
- Two things the port had to get right: the tick compares the full
  post-decrement register (durations above 127 exist -- vulcan_fireball
  holds a frame 255 ticks -- so no signed-byte view of the countdown),
  and every shipped animation ends its stream with `0x80` exactly on its
  last frame (scanned all assets/*.bin: no mid-stream use, none missing).
- Verification: full harness table vs pre-change baseline differs in
  exactly one line -- cursor isolated 3/3/170 -> 1/1/170, same alignment
  (offset 237, origin 8), same single compared frame k=97 (canon 112): the
  documented canon mid-frame tile transfer sampled 3px vs 1px across
  captures (solo runs: baseline 3, port 1, 1; one busy-box run additionally
  tore 9px at k=37, never reproduced). All other isolated rows 0,
  windowclose 0/0/40, integrated rows byte-identical incl. opening
  72499/2691 and field 158950/5621. Oracle PARITY identical: wave first
  divergence enemy_anim k=24 (mm_* k=43), mettaur no divergence (70/70).

---

## 2. Object dispatcher (T1/T3 tables → per-type entries → AI dispatch)

### 2.1 Entry routines (verified symbols)

| symbol | file:line | role |
| --- | --- | --- |
| `T1BattleObjectJumptable` | asm00_1.s:1891 | object table: T1 category → `t1_0xXX` handler |
| `T3BattleObjectJumptable` | asm00_1.s:2087 | object table: T3 category → `t3_0xXX` handler |
| `t1_0x0_80B81EC` | asm31.s:15 | shared T1 entry: `ActorType` 3-way (virus → `battleObject_dispatch_8108F50`, navi → `sub_80F2330`, player → `playerObject_main_80EA460`) |
| `t3_0x0_80C4E58` | asm31.s:27691 | canonical chip-effect entry (buster/cannon spawn: `sub_80C4E7C`/`sub_80C4F02`) |
| `t3_0x16_80C6B40` | asm31.s:31413 | shockwave-segment entry (hop-spawns a new object per tick) |
| `battleObject_dispatch_8108F50` | asm31.s:169291 | virus dispatch: `CurState` 3-table (`sub_8016F56` / `battle_8108F74` / `sub_8016C4E` via `off_8108F68`) then unconditionally `sub_8016E64` (attack-anim driver) |
| `battle_8108F74` | asm31.s:169314 | per-frame enemy body: `sub_81095D0`, `sub_801ABB8`, `NameID` gates, then AIIndex → `battle_801B1C4` + behavior table `off_8109050` + attack table `off_81091D0` |
| `battle_801B1C4` | asm00_2.s:23679 | common battle-object path: pause/collision/HP/death/flag/timestop/flash bookkeeping, then `RunAIAttack` (or `sub_8016BFC` in timestop) |
| `RunAIAttack` | asm00_2.s:24781 | VM opcode dispatch: `CurAction < 0x10` → per-type table (`CurAction * 4`); `>= 0x10` → `AIAttackJumptable` (`(CurAction-0x10) * 4`), gated by `Unk_1d == 1` else `sub_80EAD9C` |
| `AIAttackJumptable` | asm31.s:107660 | shared `0x10+` attack table (`sub_80EB04C`, …, `megamanChargeShotAiAttack_80EBE00`, `bubbleShotAttack_80ECBB0`, `tornadoAiAttack_80ED454`, …) |
| `off_8109050` | asm31.s:169420 | per-AI behavior table, indexed by `AIIndex * 4` (e.g. `0x04` Mettaur → `ForMettaur_8109EF4`) |
| `off_81091D0` | asm31.s:169615 | per-AI attack table (mostly `nullsub_13`; Mettaur entry is null — it attacks through `off_8109050` instead) |
| `ForMettaur_8109EF4` | asm31.s:170982 | Mettaur `CurAction` table (`0x00` spawn `RunSpawnAnimationMaybe_8016380`, `0x08` `sub_8109FD6`, …) |
| `sub_8109CE6` | asm31.s:170689 (`off_8109CF8` 4-state move sequencer: `sub_8109D08`/`sub_8109D70`/`sub_8109D98`/`sub_8109DBA`) | Mettaur move "script" |
| `sub_8109DD2` | asm31.s:170814 (`off_8109DE4`: `sub_8109DEC` / `sub_8109E4A`) | Mettaur shockwave "script" |
| `sub_8109DEC` | asm31.s:170830 | shockwave fire: `CurAnim=1`, timer `0x40`, fires `sub_80C6CE4` at timer `0x1B`, exits at 0 |
| `sub_800FB54` | asm00_2.s:1995 | `object_setAttack2`'s caller on the dispatch path (F5b trace) |
| `dispatch_801DACC` | asm00_2.s:29123 | second dispatch on the path (custom/gauge side) |

`battleObject_dispatch_8108F50` has zero static `bl` sites: it is reached
only through `off_8108204` from `t1_0x0_80B81EC`. `battle_801B1C4` has
exactly one (`asm31.s:169399`, inside `battle_8108F74`); `RunAIAttack`
has two (inside `battle_801B1C4`'s tail and `sub_801B394`,
asm00_2.s:23947).

### 2.2 Callers in the coverage tables

`battle_full`: `t1_0x0_80B81EC` rank 53 (1528 calls, frame 148),
`sub_8016E64` rank 67 (1146), `battleObject_dispatch_8108F50` rank 68
(1146, frame 148), `battle_801B1C4` rank 70 (1143, frame 149),
`sub_800FB54` rank 579 (25 calls, frame 437), `dispatch_801DACC` rank 658
(9, frame 265), `sub_8109CE6` rank 464 (69, frame 438), `sub_8109DD2`
rank 539 (46, frame 478), `sub_8109DEC` rank 616 (16, frame 514),
`t3_0x0_80C4E58` rank 731 (4, frame 483). `mettaur`: dispatch rank 114,
`sub_800FB54` rank 351, `dispatch_801DACC` rank 462 (per the ranking
header). `t3_0x16_80C6B40` has no row in either table — shockwave-row
coverage is a gap (the `chip-*` harness rows never spawn a hopping
shockwave segment through it; `src/shot.rs` reimplements it by hand).

### 2.3 Port order

1. `battle_801B1C4` (asm00_2.s:23679-23940ish): the common path every
   object shares; data read — `BattleObject` (`CurState/CurAction/Panel/
   HP/flags`, `BattleObject.inc:40-101`), `CollisionData`, `AIData`.
2. `battleObject_dispatch_8108F50` + `battle_8108F74` + `RunAIAttack`
   (pure control flow over ROM tables `off_8108F68`/`off_8109050`/
   `off_81091D0`/`AIAttackJumptable`).
3. Object tables `T1BattleObjectJumptable`/`T3BattleObjectJumptable` with
   the `t1_0xXX`/`t3_0xXX` entries needed by the harness rows first
   (`t3_0x0` buster/cannon, `t3_0x12` vulcan seed, `t3_0x16` shockwave).
4. Mettaur family as the first full per-type port (`ForMettaur_8109EF4`,
   `sub_8109CE6`, `sub_8109DD2`/`sub_8109DEC`, guard seq `sub_8109E7A`
   (asm31.s:170908);
   data read — `AIAttackVars` (`Unk_00` seq state, `Unk_10` timer,
   `Damage`, `Unk_30` hit-flag slot), `byte_8109D60` move table.

### 2.4 Trace verification

- Scenarios: `mettaur` (Mettaur dispatch + move/shockwave seqs),
  `cannon`/`chip-*` rows (t3 spawn/update/destroy), `battle_full` §148+
  for the joined path.
- Fields: oracle PARITY `mm_state_action` (`0x0203a9b8+0x08/+0x09`),
  `enemy_state_action` (`0x0203ab68/69`), `mm_panel_x/y`,
  `enemy_panel_x/y`, `mm_timer` (`+0x20`), `rng_cadence`
  (`0x020013f0`, one `GetRNG` step/frame/side) — via
  `python3 tools/oracle.py mettaur|wave`. Probe spot-checks:
  `probe.py watch … 0x0203a9b8:30` (MegaMan `+0x08..+0x26`) and the enemy
  slot to catch `CurAction` transitions (`0x08`→`0x09…`) the dispatch
  performs.
- What it replaces: `src/ai.rs::MettaurState` (hand-written 5-state
  decide/wander/hop/shockwave/guard loop + `Rng` + `cross_targets`), the
  chip-object lifecycles in `src/shot.rs` (`buster`/`cannon`/`vulcan`/
  `shockwave`, `just_hopped`/`just_arrived`/`departing`), and the
  `t3_0x0`-spawn bookkeeping cited in `src/shot.rs:6-9`
  (`sub_80C4E7C`/`sub_80C4F02`, `byte_80C6B00`).

---

## 3. Script VMs (map-script + chatbox text-script opcode dispatch)

Canon has two true bytecode VMs with fetch–table–dispatch loops. Neither
runs battle logic; both appear in `battle_full` because frames 0–~60 are
still the overworld (the `overworld_net.state` walk-up), and the chatbox
VM additionally drives in-battle text (chip descriptions). Battle chips
and enemies are driven by §2's table dispatch, not by these VMs.

### 3.1 Map-script VM

| symbol | file:line | role |
| --- | --- | --- |
| `MapScriptCommandJumptable` | map_script_cutscene.s:3 | opcode table (`MapScriptCmd_end` = `0x00` return, map_script_cutscene.s:79; jump-if-flag/chip/battle-result families, `MapScriptCmd_call_native_function`, gfx-anim/sound/flag writers, …) |
| `RunContinuousMapScript` | map_script_cutscene.s:1365 | loop: `ldrb opcode; lsl 2; call table[opcode]` on `eMapScriptState→ContinuousMapScriptPtr`, repeat while handler returns nonzero |
| `RunSecondaryContinuousMapScript` | map_script_cutscene.s:1389 | same for the secondary pointer (null-checked) |
| `MapScriptCmd_cmd_8035cf8` | map_script_cutscene.s:750 | one opcode handler (representative; entry suffix-less, body under interior anchor `off_8036090`, map_script_cutscene.s:1415 = `eMapScriptState` word) |
| state | `reference/bn6f/include/structs/MapScriptState.inc` (`oMapScriptState_ContinuousMapScriptPtr`, `…_Secondary…`) | |

Coverage: body executed in `battle_full` (anchor `off_8036090`, 14457
instr from frame 0, 0 entry-calls — suffix-less entry, same attribution
limit as §1) but in **no** harness row's scenario (it is the overworld
walk-up, which no row replays). Zero static `bl` sites for the handler;
the loops are called every frame from the map main loop.

### 3.2 Chatbox text-script VM

| symbol | file:line | role |
| --- | --- | --- |
| `chatbox_runScript` | chatbox.s:942 | init: `(archive, script_idx)` → resolve offset table, set cursor/current-script pointers, print speed, tile state |
| `chatbox_runScript_803FE10` | chatbox.s:178 | per-frame step (body under interior anchor `off_803FEB0`, chatbox.s:266) |
| `chatbox_runScript_803FD9C_on_eTextScript201BA20` etc. | asm36.s:4179, chatbox.s:63-236 | entry variants (fixed archive / white-dot setter) |

Coverage: step body executed in `battle_full` (anchor `off_803FEB0`,
3689 instr from frame 0), in no harness row. 93 static `bl` init sites
(mostly map-side text triggers).

### 3.3 Port order (lowest priority of the three — map-only)

1. `RunContinuousMapScript` loop + `MapScriptCommandJumptable` indexing +
   `eMapScriptState` pointer stepping; data read — ROM map-script blobs
   (opcode bytes + inline operands).
2. The ~70 opcode handlers in frequency order (jump-if family first —
   they dominate the `battle_full` instruction count).
3. Chatbox init + step; data read — `TextScriptArchive` blobs
   (u16 offset table + script bytes).

### 3.4 Trace verification

- Scenario: `battle_full` frames 0–60 (the only profiled scenario that
  executes either VM). A dedicated probe — `probe.py watch bn6f_real.gba
  60 0x02011E60:16` (`eMapScriptState`, word at `off_8036090`) with
  `--loadstate overworld_net.state` — watches the script pointers step;
  no oracle PARITY field covers VM state (gap: oracle watches battle
  objects, RNG, gauge only).
- What it replaces: nothing in `src/` yet — no map or chatbox code
  exists. Porting either VM is blocked first on a harness row that covers
  it (overworld walk-up row), which is itself blocked on the uncovered-set
  queue (`battle_full.md:1171+`: `npc_dispatch_809E570`,
  `checkOWObjectInteractionAreasOverlap_8003894`, …).

---

## Appendix: verifier cross-check list

Every symbol the verifier checks against the disassembly, with the
coverage-table evidence behind it:

- `sprite_loadAnimationData` (sprite.s:4), `sprite_update` (sprite.s:28),
  `_sprite_loadAnimationData` (asm38.s:1667), `_sprite_update`
  (asm38.s:1722), `object_updateSprite` (asm00_2.s:25045),
  `UpdateBattleObjectSprite` (asm00_2.s:25144),
  `sub_80028C0` (sprite.s:359, rank 25/27 — bookkeeping, not the player).
- `T1BattleObjectJumptable` (asm00_1.s:1891),
  `T3BattleObjectJumptable` (asm00_1.s:2087),
  `t1_0x0_80B81EC` (asm31.s:15, rank 53),
  `battleObject_dispatch_8108F50` (asm31.s:169291, rank 68/114),
  `battle_801B1C4` (asm00_2.s:23679, rank 70),
  `RunAIAttack` (asm00_2.s:24781), `AIAttackJumptable` (asm31.s:107660),
  `off_8109050` (asm31.s:169420), `off_81091D0` (asm31.s:169615),
  `ForMettaur_8109EF4` (asm31.s:170982),
  `sub_8109CE6` (rank 464), `sub_8109DD2` (rank 539),
  `sub_8109DEC` (asm31.s:170830, rank 616),
  `t3_0x0_80C4E58` (asm31.s:27691, rank 731),
  `t3_0x16_80C6B40` (asm31.s:31413, no row — gap),
  `sub_800FB54` (asm00_2.s:1995, rank 579/351),
  `dispatch_801DACC` (asm00_2.s:29123, rank 658/462),
  `sub_8016E64` (asm00_2.s:17420, rank 67).
- `MapScriptCommandJumptable` (map_script_cutscene.s:3),
  `RunContinuousMapScript` (map_script_cutscene.s:1365),
  `MapScriptCmd_cmd_8035cf8` (map_script_cutscene.s:750, body anchor
  `off_8036090` :1415, 14457 instr), `chatbox_runScript` (chatbox.s:942),
  `chatbox_runScript_803FE10` (chatbox.s:178, body anchor `off_803FEB0`
  :266, 3689 instr).
