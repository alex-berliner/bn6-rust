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

Empty on purpose: nothing wave 2's harness has produced yet is allowlisted.
`audio` stays out of tools/harness.py entirely for now (AUDIT.md's "Parked"
section) rather than being carried in here at its old regress.py `want` of
7303 -- that number belongs to the old boxed/residual-RMS check, not to a
full-screen pixel count, and re-deriving it is wave 3's job when audio comes
off the parked list.
"""

ALLOWLIST = {}
