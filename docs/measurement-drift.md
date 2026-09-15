# Measurement drift: the envelope, its mechanism, and the verify_rows policy (F48)

Ticket F48. Measurement base: commit `ed9c9c1` (branch `wt/f48-drift-envelope`), one tree, never
moved during measurement. Rust ROM built from it: sha256 `1997be3b4e8f463a…`
(`/tmp/bn-4df388b0/h_rom_.gba`). F45's landed tree `1c49bc5` and F46's branch tip `5e2499a` both
build sha256 `ab80121ec3a65e65…` — **byte-identical to each other, and byte-identical to the ROM
still sitting in F46's own session scratch** (`/tmp/bn-527974a1/h_rom_.gba`, keyed by
`sha1("/tmp/bnwt/f46-backdrop-registers")`, mtime 18:28 today). Everything below follows from that.

## 1. The envelope table (row × run, same commit, four runs, two sessions)

Four runs of `--only field,opening,gunner,mettaur --no-gallery` on `ed9c9c1`: two in session A,
two in session B (every run a fresh process; sessions separated by the step-2 captures). A fifth
mettaur warmup run agreed too.

| row · ui | run 1 | run 2 | run 3 | run 4 | min / max / spread |
|---|---|---|---|---|---|
| field · integrated (total/worst/neg) | 158930/5601/261029 | 158930/5601/261029 | 158930/5601/261029 | 158930/5601/261029 | **spread 0** |
| field · isolated | 0/0/1139 | 0/0/1139 | 0/0/1139 | 0/0/1139 | spread 0 |
| opening · integrated | 18740/647/98649 | 18740/647/98649 | 18740/647/98649 | 18740/647/98649 | **spread 0** |
| opening · isolated | 0/0/86591 | 0/0/86591 | 0/0/86591 | 0/0/86591 | spread 0 |
| gunner · isolated==integrated | 2105613/38237/2284867 | same | same | same | **spread 0** |
| mettaur · isolated (control) | 0/0/41734 | same | same | same | spread 0 |

**Runs needed to see any movement: 4 of 4 saw none.** On the same commit the harness is
run-to-run deterministic to the pixel, including the negative totals — on the FIVE rows measured
here. That is NOT a harness-wide claim, and the landed record carries its own counter-example:
Q3's merge `184b9b5` documents `cursor` reading `1/1/170/186279` and then `13/12/170/186277` at
the SAME commit (`7cd1ec1`), called capture instability at the time and deliberately not gated.
Honest boundary: five rows measured deterministically, `cursor` not, and no per-run build
identity (ROM sha256 + /tmp input hashes) was recorded alongside any of these runs — that
omission is exactly what let F45's 158935 become un-reproducible (§6).

## 2. per-capture or per-frame? (field-bg2, kept dirs in /tmp/bn-f48/)

`field-bg2` re-captured twice through the row's own `harness.run()` (same commit, same Sides,
same `Align(canon_ref=135, rust_offset=113, search=None)`), dirs kept
(`/tmp/bn-f48/bg2_run1`, `/tmp/bn-f48/bg2_run2`; the harness's `run_check` deletes dirs, `run()`
does not):

- The row reads **4800 both runs** (F45 landed 4560, F46 saw 5280).
- Run-vs-run, SAME side, frame by frame: rust 121+k vs rust 121+k = **0 on all 40 k**; canon
  135+k vs canon 135+k = **0 on all 40 k**. The captures are byte-identical across runs.
- The row's whole diff is **one frame, k=0** (the boundary frame), and it is exactly the top
  **20 scanlines** (y 0..19, 240 px each). The historical values 4560 / 4800 / 5280 are 19 / 20 /
  22 whole 240-px rows: **the drift on this row is a whole-scanline-band change on one frame,
  quantized in screen rows — not per-capture scatter.**

## 3. Symmetric or one-sided? — neither: it tracks input versions, not run order

Every delta against a fixed point, in measurement order:

| comparison | ROM bytes | field total | Δ | bg2 |
|---|---|---|---|---|
| F45 landed line (session ~18:16) | ab80121e… | 158935/5606/261034 | — | 4560 (19 rows) |
| F46 session 18:28 | ab80121e… | 158953/5624/261052 | **+18** | 5280 (22 rows) |
| F48 session ~19:15, old ROM re-run in F45's tree | ab80121e… | 158953/5624/261052 | **+18, exactly F46's** | 5280 — **also exactly F46's** (command 12) |
| F48 session, own tree ed9c9c1 (T17/T19 chips) | 1997be3b… | 158930/5601/261029 ×4 | **−23 vs old ROM** | 4800 (20 rows) |
| coordinator "today's main" (ticket text) | ? | 158928 | −2 vs F48's new-ROM reading | ? |

Signs: +18, 0 (F46 vs F48 on identical bytes), −23, −2 — **mixed, not one-sided**. A monotone
cause in the capture path is excluded; for completeness, the sampling point is
`tools/mgba_capture.c`: frames are `core->runFrame(core)` at `:943`/`:945`, the framebuffer is
written by `write_frame` (`:205`) from the buffer installed with `setVideoBuffer` (`:299/:374`) —
i.e. the picture is sampled once per `runFrame` return, in lock-step, with no wall-clock or
`SDL_Delay` read anywhere in the sample path. Nothing there can drift ±18 px between runs, and it
does not: the deltas above are constant across total, worst AND negative (+18/+18/+18, then
−23/−23/−23), which is the signature of **one frame's content changing between input versions**,
not of sampling noise (sampling noise would scatter total without moving worst equally).

**Verdict (revised — the first headline, "the movement is built-ROM-version skew", over-claimed
and is withdrawn):** Same-ROM captures are pixel-deterministic on `field`, `opening`, `gunner`,
`mettaur` and `field-bg2` (0 of 373 kept frames differ across two real re-captures, both sides,
verified independently), so the movement is NOT sampling drift. Part of it is a version event:
T17/T19's ROM change (`ab80121e…` → `1997be3b…`) deterministically moves `field` by −23 on one
frame and `field-bg2` from 22 to 20 whole-scanline rows. The F45→F46 movement (158935 → 158953,
4560 → 5280) is NOT that — both trees build byte-identical ROMs (`sha256sum
/tmp/bn-f48/rom_f45tree.gba rom_f46tree.gba` → the same `ab80121e…`) — so ROM version is
variable-free there and the cause remains **UNNAMED**. The leading candidate is a canon-side
input version that existed at 18:16 and no longer exists: the 18:41 `restore_inputs.sh` is AFTER
F46's 18:28 run — which already reads the new numbers — and reproduces F46's numbers exactly,
which exonerates the restore itself. This **half-discharges** the "root cause unchecked"
verdict, not discharges it: determinism is proven and one version event is named; the F45→F46
input version is not. The commit pair to diff if the hunt reopens: `1c49bc5`..`ed9c9c1` for
`src/ vendor/ assets/` (the −23, already explained by T17/T19); the +18 lives in the /tmp input
history, which git cannot see.

`opening integrated 18740/647/40` and `gunner 2105613/38237/130` reproduce EXACTLY across both ROM
generations and at least four independent sessions — the constants F44 was landed on are stable
far outside any plausible band; they were never at risk from capture noise.

## 4. The policy (implemented in tools/verify_rows.py, and only there)

`verify_rows.py --with-main [ref]` (default ref `main`; without the flag, behavior is unchanged):

- A `--expect` on a row whose `Align.search` is a range, whose expected **total is not 0**, and
  which appears in `DRIFT_ENVELOPE` with envelope > 0, that does not match any of the row's
  harness lines exactly, is reported `MATCH (drift-band, main=<main total> exp=<exp total>)`
  instead of FAIL iff, **same-session**: `|exp_f − main_f| ≤ envelope` and
  `|branch_f − main_f| ≤ envelope` for every pinned numeric field (total/worst/negative);
  `frames` must be equal exactly on both sides. The branch differing from same-session main by
  more than the envelope FAILS as before; so does an expect differing from main by more than the
  envelope.
- **A row whose expected total is 0 is never widened** (its failure is a real signal), and
  neither side of a banded comparison may be BLIND. Exit-code semantics unchanged: PASS only when
  every row is matched or drift-banded. The envelope in force is printed.
- Envelope table (pixels): **field = 25** — provenance: peeked, and NOT one measured delta: the
  max of FOUR recorded field-integrated totals — 158928 (coordinator/main, reproduced by no run
  ever), 158935 (F45 landed), 158953 (F46 + this ticket's old-ROM re-run), 158930 (this ticket
  ×4 on the new ROM) → 158953−158928 = 25. Of that, only **23 is reproduced** (the T17/T19 ROM
  change, deterministic ×4); the outer **2 px exist only to cover 158928**, which nobody has
  reproduced. The same-commit measured spread is 0; the band covers recorded-constant skew
  across trees and input versions, the only skew ever observed. **Consequence: a real tree-side
  regression of up to 25 px on `field` bands through** when branch == main; anything larger
  fails and forces the constant to be re-recorded. Every other row: absent → 0 → no banding
  (strict). field-bg1/bg2/bg3 are structurally excluded (`search=None`, pinned pairing).
- Mechanics, so the next reader does not re-derive them: the `search=None` exclusion is read at
  RUNTIME from the measured tree's own `Align` config (`_searched_rows` imports that tree's
  `tools/harness.py`; import failure returns `{}` → the band is disabled — fail-closed, back to
  strict). And a zero total can never be banded: `_try_drift_band` returns None immediately
  when `env <= 0 or want[0] in ("-", "0")` — a zero row's failure is a real signal.
- Auxiliary fix, needed so the at-risk class is gateable at all: an expectation is now matched
  against ANY of the row's harness ui lines, not only the first printed one. Before this,
  `--expect opening=18740/647/40/98649` (the integrated line every report quotes) ALWAYS read
  MISMATCH because verify_rows compared the isolated line (0/0/40/86591) — visible in F43's
  worklog landing attempt. Gates that pass today still pass; no land.sh call breaks.
  The flag is new (`--with-main`); it is off by default, so existing calls are untouched.

Known limitation, stated: with envelope 25, the real tree-side −23 (T17/T19) between ROM
generations is inside the band, so a constant recorded on the old ROM bands through on the new
ROM when branch == main. That is the policy working as specified (the branch-vs-main guard is
what catches real regressions); a future tree change LARGER than the envelope fails the gate and
forces the constant to be re-recorded. With the corrected accounting above: 23 of the 25 px are
a reproduced, named event; the outer 2 px cover the never-reproduced 158928.

## 5. The band is DIAGNOSTIC-ONLY, and the same-tree invocation is a trap

`tools/land.sh` does not pass `--with-main` — its only call site passes `--expect` — so today's
landing gates are untouched. That is the only reason a numeric band coexists with AGENTS.md's
"never a tolerance".

The trap, named: in `verify_rows.py`, `if main_sha == sha: main_results = results`. With
`--with-main` pointing at the branch's own ref (or any ref resolving to the same commit),
"main" IS the branch's own measurement and the band degenerates into a plain one-sided ±25
tolerance on the branch's own number — exactly the widened-tolerance gate AGENTS.md forbids.
**Rule: `verify_rows … --with-main` is a diagnostic and may never be a landing gate. If
`--with-main` is ever wired into `land.sh`, that change needs its own ticket and an explicit
owner decision.**

## 6. What the enabling fix reveals about two LANDED merges (read before re-quoting F44/F45 numbers)

Before this ticket's auxiliary matcher fix, `parse()` kept ONE line per row — the first printed,
which for a `ui=both` row is the ISOLATED line — so an integrated claim could never MATCH a
gate: the comparison always ran against the isolated line. Consequences, precise:

- `gunner`'s `2105613/38237/130` MATCH at F44 DID check real pixels: that row's isolated and
  integrated lines are numerically identical, so the isolated line it matched carries the same
  numbers.
- **F44's `opening integrated 18740/647/40/98649` and F45's `field integrated
  158935/5606/40/261034` were never machine-gated.** The recorded gate lines are `opening PASS
  0/0/40/86591 MATCH` and `field PASS 0/0/40/1139 MATCH` — the isolated ones. No merge needs
  reverting; both constants must be treated as REPORT-ONLY until re-gated under the fixed
  matcher. F45's `158935/5606` — the one total on either tree that no run has reproduced — is
  now most plausibly a carried-forward quote rather than a measurement of `1c49bc5`.

Rule, every landing from here on: **a landing that quotes a non-zero expected total must also
quote the sha256 of the built ROM and of every /tmp canon input it was measured against, and
must name which harness ui line (isolated or integrated) the gate matched; a number without its
build identity is a report quote, not a gate.**
