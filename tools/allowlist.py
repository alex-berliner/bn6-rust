#!/usr/bin/env python3
"""Known, ticketed defects the harness (tools/harness.py) tolerates instead of
hiding them (AUDIT.md pair 11).

Dropping `want` means a non-zero result is a failure, full stop -- there is
no number a check can settle on and be called "ok". A defect that is
understood and not yet worth fixing goes here instead, named and dated, and
still prints as FAILED (allowed: TICKET) in the summary. It never prints ok,
and it is never silent: raising the bar back to 0 (or lowering `max_px`) is
how a fix gets noticed by the suite instead of just by whoever made it.

Format: {key: (max_px, "TICKET-ID", "YYYY-MM-DD")}

`key` is either a bare check name ("audio"), which allows that many px on
every ui variant of the check, or "name:ui" ("audio:integrated"), which
allows it only for that one variant -- the more specific key wins if both
are present. `max_px` is the largest single-frame differing-pixel count the
run is allowed to reach; anything higher is a regression past the known
defect, not a tolerated instance of it, and is reported as a plain FAILED
rather than FAILED (allowed: ...).

`audio` stays out of tools/harness.py entirely for now (AUDIT.md's "Parked"
section) rather than being carried in here at its old regress.py `want` of
7303 -- that number belongs to the old boxed/residual-RMS check, not to a
full-screen pixel count, and re-deriving it is wave 3's job when audio comes
off the parked list.

Wave 3 (migrate-checks, 2026-09-08): every entry below is an INTEGRATED
number (AUDIT pair 9's "everything on" run), never an isolated one --
per the ticket, an isolated failure is reported, not allowlisted (there is
no "known defect" to name yet when the isolated run itself has not been
driven to 0). `worst` here is each check's own worst single-frame count
from a live run this session; `max_px` gives it a little headroom (not a
round number chosen to look tidy) rather than pinning the exact observed
value, so an unrelated 1-pixel jitter does not immediately need a new
ticket. All are AUDIT-6 (full screen surfacing what the old per-check box
never measured), dated the day this ticket ran them.
"""

ALLOWLIST = {
    # tiles/gauge integrated (worst 3468/8 frames): TODO A8, the custom
    # gauge's stripe-flow animation not yet modelled (TRANSFER.md 1270),
    # PLUS the sprites (navi, enemy, hand icon) this ui variant turns back
    # on, over regress.py's old demo-hudmatch capture. tiles and gauge are
    # the SAME full-screen capture (see _tiles_gauge()'s own note) so they
    # share one ticket.
    # field/warp/buster/chip-use integrated (worst up to 30674): the HUD
    # (HP box, gauge) this ui variant turns back on has never been compared
    # against a genuinely empty (zero-enemy) arena before -- `tiles`/`gauge`
    # only ever checked it against demo-hudmatch's ONE-enemy arena. Isolated
    # (backgrounds/sprites only, no HUD) is clean or near it on all four;
    # this is new coverage, not a regression, and is reported rather than
    # investigated further within this ticket's scope.
    "field:integrated": (28000, "AUDIT-6: HUD vs a zero-enemy arena, not compared before", "2026-09-08"),
    "warp:integrated": (19500, "AUDIT-6: HUD vs a zero-enemy arena, not compared before", "2026-09-08"),
    "buster:integrated": (28000, "AUDIT-6: HUD vs a zero-enemy arena, not compared before", "2026-09-08"),
    # chip-use re-titled by F41 (2026-09-15, NEGATIVE): the AUDIT-6 text was
    # wrong for this row -- isolated (OBJ+HUD) reads 0, so the residue is not
    # the HUD: ~8000/frame of BG1 backdrop-art mismatch (k=0..23) plus canon's
    # RESULT window slide-in on BG3 (k=24..29, one 16-px column per frame,
    # resultWindowSlideTick_802BE36, asm03_0.s:11701) that our never-resolving
    # zero-enemy fixture cannot draw (F38b's RESOLVE_OVER retry measured worse;
    # T7w's split: full 275307 / BG3-only 44306 / BG1-only 443520). See
    # docs/worklog/F41.md. max_px and date unchanged.
    "chip-use:integrated": (28000, "BG1 backdrop art + canon's RESULT window on BG3 (F41 NEGATIVE 2026-09-15: total 275307, not 2; band = resultWindowSlideTick_802BE36 16px/frame, rust side never resolves)", "2026-09-08"),
}
