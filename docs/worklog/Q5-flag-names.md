# Q5 — Retire the dead `FLAG_*` names in tools/harness.py's row notes; document SceneFlags' raw-byte escape hatch

Branch `wt/q5-flag-names`, cut from 35e6efa. Comment-and-doc ticket: no behaviour change allowed.

## Baseline (before any edit, 35e6efa, own build via tools/worktree.sh env)

`python3 tools/harness.py --only mettaur,result,opening,popup --no-gallery`:

- opening  isolated PASS total 0 worst 0 frames 40  | negative: not blind (total 86591)
- mettaur  isolated PASS total 0 worst 0 frames 70  | old-box 0, outside 0 (0%) | negative: not blind (total 41734)
- result   isolated PASS total 0 worst 0 frames 40  | negative: not blind (total 111839)
- popup    isolated PASS total 0 worst 0 frames 80  | negative: not blind (total 1288)

All four 0/0 with the ticket's predicted non-blind negatives. (The run also prints
`opening integrated FAILED total 25829` — that is the field-integrated mode the ticket
does not ask for and a pre-existing allowlisted state, not touched here.)

Build note: with `CARGO_TARGET_DIR=/tmp/ct_q5-flag-names` exported, the ELF lands at
`/tmp/ct_q5-flag-names/thumbv4t-none-eabi/release/bn` (not the repo-relative `target/...`
path AGENT_GUIDE's command assumes) — gbafix.py needs that path.

## Step 1 — the 13 comment spots

Before: `grep -n "FLAG_[A-Z_]*" tools/harness.py` → 13 hits on 13 lines
(1195, 1343, 1451, 1461, 1489, 1800, 1801, 1985, 2163, 2812, 2888, 2911, 2960).
After: 0 hits. Every rewrite is `FLAG_<NAME>` → `SceneFlags::<NAME>` inside a `#`/`#:`
comment or a row-note string; no number changed, no non-comment text changed.
Line 1489's code part (`ZERO_ENEMY_RESOLVED = dict(ZERO_ENEMY, flags=0x31)`) is
byte-identical — only its trailing comment changed. Verified with the ticket's own
check (`git diff -U0 | grep '^[+-]' | grep -v '^[+-][+-]'`): all 13 changed pairs
are comment/string-only.

## Step 2 — From-impl docs (src/fixture.rs)

Two doc comments added on `From<u8> for SceneFlags` and `From<SceneFlags> for u8`:
they exist for the harness's poke/cheat path (the descriptor at 0x02000040 is bytes),
not for call-site bit tests (`f.flags.0 & 0x20`); call sites use the named consts and
accessors. No code inside the impls changed.

## Verification after rebuild (step 2)

Rebuild (`Finished` warm, 5.2s) produced a **byte-identical** ROM
(`cmp -l baseline.gba new.gba` → 0 differing bytes; not even panic-line bytes moved).
`--only mettaur,result,opening,popup --no-gallery` after:

- opening  isolated PASS total 0 worst 0 frames 40  | negative: not blind (total 86591)
- mettaur  isolated PASS total 0 worst 0 frames 70  | old-box 0, outside 0 (0%) | negative: not blind (total 41734)
- result   isolated PASS total 0 worst 0 frames 40  | negative: not blind (total 111839)
- popup    isolated PASS total 0 worst 0 frames 80  | negative: not blind (total 1288)

Identical to baseline. `grep -c "FLAG_[A-Z_]" tools/harness.py` → 0.

## Ideas dropped / notes for the next worker

- None of the 13 hits needed a NEGATIVE: each had an exact `SceneFlags` const or
  accessor counterpart (Q2's newtype covers all eight bits the notes name).
- src/spr.rs `FLAG_ACTIVE` / src/script.rs `EVENT_FLAG_*` deliberately left alone
  (ROM facts, ObjectHeader.inc:8-12, asm03_0.s:18525; ticket forbids folding them in).
- "Three oldest" hits (grep order): 1195, 1343, 1451 — quoted before/after in the
  report.
