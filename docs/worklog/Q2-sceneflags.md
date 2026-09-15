# Q2 — SceneFlags newtype (scene's switches as a flags type)

Ticket: turn the fixture descriptor's flags byte (src/fixture.rs `FLAG_*` free consts +
`Fixture::flag(bit)`) into `pub struct SceneFlags(u8)` with named bit consts and accessors.
Behaviour-neutral; .gba may differ only by panic-line bytes. Byte layout is the contract
(harness pokes it into RAM; battle.rs:2320's BLANK_HUD == BLANK_BACKDROP note must keep reading
the same value).

## Baseline (before any edit), HEAD 5ab1275, worktree wt/q2-sceneflags, --ui isolated

```
opening    isolated    PASS    total 0  worst 0  frames 40   | negative: not blind (total 86591)
mettaur    isolated    PASS    total 0  worst 0  frames 70   | old-box 0, outside 0 (0%) | negative: not blind (total 41734)
field      isolated    PASS    total 0  worst 0  frames 40   | negative: not blind (total 1139)
cursor     isolated    FAILED  total 1  worst 1  frames 170  | negative: not blind (total 186279)
```

cursor total 1/worst 1 at frame 170 is HEAD's own known single-frame tear (per coordinator note:
HEAD's cursor row is the baseline; the tear moves with ROM layout and is reported, not chased).

## Change (step 1, this commit)

- src/fixture.rs: added `pub struct SceneFlags(u8)` (`Clone, Copy, PartialEq, Eq`) with
  associated consts `OPEN_WINDOW`/`BLANK_HUD`/`BLANK_BACKDROP`/`AUTO_FIRE`/`SKIP_INTRO`/
  `RESOLVE_OVER`/`HUD_LIVE`/`TRACE` (same bit values 1<<0..1<<7, docs + provenance lines moved
  verbatim from the free consts) and `const fn` accessors `open_window/blank_hud/blank_backdrop/
  auto_fire/skip_intro/resolve_over/hud_live/trace`, plus `From<u8>`/`From<SceneFlags> for u8`.
  `Fixture.flags: u8` -> `SceneFlags`; `read()` wraps with `SceneFlags::from(r8(19))`;
  `trace_enabled()` reads `SceneFlags::from(r8(FLAGS_OFFSET)).trace()`. Deleted the free
  `FLAG_*` consts and `Fixture::flag(bit)`.
- src/battle.rs, src/main.rs: all 14 `f.flag(fixture::FLAG_X)` call sites -> `f.flags.x()`
  accessors (battle.rs 1616/1628/1833/1836/1982/2021/2123/2512/2523/2976/4130/4139/4153;
  main.rs 273). Comment mentions of the old `FLAG_*` names renamed to the new const names
  (comment-only).
- FIXTURE.md, tools/harness.py untouched; byte assignment unchanged (bits 0..7 same values).

## Result (after, same command, same target dir, commit dfaeaa5)

```
--ui isolated (both runs, byte-identical to baseline):
opening    PASS     total 0  worst 0  frames 40   | negative: not blind (total 86591)
mettaur    PASS     total 0  worst 0  frames 70   | old-box 0, outside 0 (0%) | negative: not blind (total 41734)
field      PASS     total 0  worst 0  frames 40   | negative: not blind (total 1139)
cursor     FAILED   total 1  worst 1  frames 170  | negative: not blind (total 186279)   <- HEAD's own tear, unchanged
--ui integrated (post-change build vs HEAD archive tree, all lines identical):
opening    integrated FAILED total 25829 worst 931 frames 40 | negative: not blind (total 105749)   <- same at HEAD
cursor     isolated   FAILED total 1     worst 1   frames 170| negative: not blind (total 186279)
field      integrated FAILED (allowed: AUDIT-6 ... <=28000) total 158926 worst 5597 frames 40      <- same at HEAD
fitted constants: 19 (derived 429, peeked 145) both sides
```

`python3 tools/verify_rows.py wt/q2-sceneflags mettaur,field,opening,cursor` (clean checkout,
run from main repo): mettaur PASS 0/0/70, field PASS 0/0/40, opening PASS 0/0/40, cursor FAILED
1/1/170 (HEAD's tear) -> verify_rows: PASS.

### .gba diff vs HEAD (one line, per the coordinator note)

Plain release builds (gbafix'd, both 583860 bytes): all 4054 differing bytes lie inside .text
(image offsets 0x1444..0x4562, i.e. `Battle::draw` and the functions immediately after it);
.rodata, .iwram, .ewram and every section size are byte-identical. The diffs are codegen jitter
around the rewritten call sites (literal-pool placements and register allocation shifted by
12 bytes / renumbered stack slots), NOT panic-line bytes alone -- wider than the ticket's
prediction, so recorded here rather than papered over. Descriptor layout unchanged: `SceneFlags`
is a single-field newtype over the same u8, so `Fixture.flags` keeps its offset/size and the
harness's RAM poke (+19) reads the same value (battle.rs:2320's BLANK_HUD == BLANK_BACKDROP
note unaffected).

## Verdict

The .gba does differ by slightly more than panic-line bytes (instruction-encoding jitter in the
touched functions), which the ticket's rules did not predict; the four acceptance rows are
byte-identical to HEAD on every line that ran, and verify_rows is PASS. Reported as-is; not
widening the change to try to shrink the diff (the jitter comes from `flag(bit)`'s runtime-mask
argument becoming a const immediate, which is the point of the ticket).

## Unverified

Nothing on the acceptance path; the residual is that the .text jitter is equivalence-argued
(same operations, different register allocation) rather than proven beyond the four rows -- other
rows (chip, popup, demo-*) were not re-run.

## Tried / dropped

- Considered keeping the free `FLAG_*` consts as aliases: dropped — leaves the bare-byte API the
  ticket is removing, and nothing outside fixture.rs used them after the call-site pass.
- Considered naming consts `SceneFlags::FLAG_X` to avoid touching comments: dropped — redundant
  prefix; comment rename is mechanical and behaviour-neutral.
- Did NOT touch src/hud.rs / src/backdrop.rs (Q1 worker concurrent) — verified neither reads flags.

## Next

- Post-change harness lines for the four rows (both UI variants), .gba diff vs HEAD's plain
  release build (name the sections), verify_rows if asked.
