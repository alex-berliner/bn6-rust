#!/usr/bin/env bash
# The day's run: launched by cron after the Charm Hyper refresh. If no coordinator is running and at least
# 100 credits are available, start an all-Hyper run (two worker-hyper slots, coordinator/verifier/recon on
# Hyper) that tools/hyperwatch.sh stops when the credits are gone. OpenRouter is a reserve: cap 0.25.
cd "$(dirname "$0")/.."
pgrep -f 'pi -p --approve --session-dir /tmp/bn-pi' >/dev/null && { echo "a run is active"; exit 0; }
python3 tools/hyper_credits.py --min 100 || { echo "fewer than 100 credits; not starting"; exit 0; }
BN_HYPER=1 BN_PI_CAP=0.25 BN_COORD_MODEL=hyper/qwen3.8-flash bash tools/pi_coordinator.sh "Run the loop with TWO workers in flight, both role worker-hyper (Charm Hyper; the user wants all 250 daily credits used and the run stops by itself when they are gone -- do not dispatch anything to the Muse worker role, OpenRouter is a reserve). Use python3 tools/next_ticket.py --pair 2. Spend floor 0.5 on OpenRouter. The phase is porting: the queue is whatever next_ticket.py returns until none is OPEN. Each landing keeps the full table identical (every isolated row 0; cursor's single-frame tear moves with the ROM layout and is reported, not chased), verified with tools/verify_rows.py and the trace as the tickets say; the verifier only when the branch merges and a claim needs it. Commits arriving on main from the human session are normal. No model overrides beyond the roles named."
