# navi — notes

## T182 (2026-09-18): first navi pattern, partial port

M6 navi slot 0x17 (ForGunner_8113078, the only navi T145 has touched) has its
per-AIIndex CurAction dispatch routed through TWO CurAction-indexed handler
tables reached from the navi-family reader `sub_80F2354`
(asm31.s:123323-123356):

1. The **think arm** = `AIThinkTables_8109050[0x17] = ForGunner_8113078`
   (asm31.s:169496, 12 entries at asm32.s:10123-10142). Reached through
   `battleObject_dispatch_8108F50`'s call to `battle_801B1C4`
   (asm31.s:169414-169415). The CurAction 0x0A arm
   (`gunnerAttackExec_8112F4E`, asm32.s:9958-10102) is ported as
   `gunner::gunner_update` (`#[allow(dead_code)]`, src/gunner.rs:412). The
   other 11 arms are NOT ported.
2. The **AI arm** = `off_80F23AC[0x17] = off_81068E8` (asm31.s:123395, 15
   entries at asm31.s:164165-164181). Reached through
   `ai_eventuallyRunsAIAttack_801AF44` (asm31.s:123345-123347). Entries
   0x00..0x07 are the shared generic CurAction arms
   (RunSpawnAnimationMaybe_8016380+1, etc.); entries 0x08..0x0E are the
   navi's own executors (sub_8106924+1 .. sub_8107750+1). AI_ARM[15] is
   ported as DATA only in src/navi.rs:159-169 (T145); no per-CurAction
   code yet.

### What's ported (data only)

- `src/navi.rs` — four 25-slot tables (THINK_TABLES, STRUCT1/2_VIRUS_PTRS,
  ACT_HANDLERS, 32 entries each, T145 cite asm31.s:169448/513/578/643).
  Plus the slot-0x17 navi-family rows (NAVI_HIT_LEG, NAVI_PATTERN_LEG,
  NAVI_ACT_LEG, AI_ARM, CURSTATE_LEGS).
- `src/gunner.rs` — `gunner_update` (the CurAction 0x0A arm of
  ForGunner_8113078, `#[allow(dead_code)]`, the per-type routine port
  complete with the 4 sub-step state machine, SHOTS/SHOT_GAP/RECOVER_FRAMES
  constants, but the actual shot/cursor/recover cycle lives on
  `Battle::gunner_ctl`).

### What's NOT ported

- CurAction 0x08 (`sub_8106924+1`) of the AI arm — the first non-shared
  CurAction in off_81068E8, the actual "first-pattern routine" the
  ticket names. Three sub-arms (`off_8106940`: sub_810694C / sub_8106964
  / sub_81069B4, asm31.s:164184-164202) all unported.
- The other 11 CurAction arms of ForGunner_8113078 (besides 0x0A) — the
  spawn/idle/materialize arms run through the shared
  `Actor::update` / `Ai::update` common path on the rust side.
- `Style::Navi` CurAction dispatch — `objects::enemy_think`'s navi arm
  is a passthrough, then `ai::Ai::update` returns early for
  `Style::Gunner | Style::Navi => {}` (src/ai.rs:264-265). The latched
  fork services the shared think arm; the per-AIIndex CurAction handler
  is NEVER called for `Style::Navi`.

### What was measured

- `navi-gunner-ai` (T182) probe row: same descriptor as `navi-gunner`,
  same canon side. Result `2092176/38237/130/2247584` — identical to
  navi-gunner (the AI arm data does not regress; the 0/0/N gate is
  unreachable without a true navi-spawn state, per T153/T166).
- verify_rows PASS on `mettaur=0/0/70/41734`, `cursor=1/1/170/186279`,
  `navi-gunner=2092176/38237/130/2247584`, `navi-gunner-ai=2092176/38237/130/2247584`.

### Next lever

- CurAction 0x0A dispatch for `Style::Navi` — wire `gunner_update` from
  `objects::enemy_think`'s navi arm when CurAction reaches 0x0A. The
  navi-gunner row's CurAction never reaches 0x0A in the measured window
  (stays at 0x04 — canon CurState_CurAction 0x0004 at frame 69), so this
  does not regress navi-gunner's numbers.
- A true-navi-spawn state (ProtoMan art + 900 HP from `byte_81067FC` /
  `byte_8106804 row 0`). Per T153/T166 the canon can't spawn a true navi
  from any encounter roll; needs a `tools/states.py` recipe that repoints
  `CurBattleDataPtr` (0x02001b9c) to a RAM-resident BattleSettings +
  formation array naming `0x0185` directly, before the spawn populates
  (T166 step 5).