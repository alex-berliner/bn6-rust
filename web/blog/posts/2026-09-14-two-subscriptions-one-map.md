# Two subscriptions, one map

The agents no longer belong to one subscription. A single configuration file now says which model does which job on which service, and the launcher, the watchers and the one-off tools all read it. Swapping a service means adding a block to that file; running two at once means listing both.

## What a run is made of

A run has four jobs: a coordinator that reads the ticket list, hands out work, checks the numbers and merges; workers that change the code in their own copies of the repository and measure the result against the recording of the original game; a verifier that checks a claim the numbers alone cannot prove; and a recon agent that maps where a behaviour lives in the original's disassembly. Each job names a list of candidate models in order of preference, from any service, and a run takes the first candidate whose service has budget at launch. If the service behind a job runs dry during the day, the run stops and comes back on the next candidate.

## The second subscription

The MiniMax coding plan was put through the same test the others took: seven archived tickets, each replayed from the commit it started from, judged by rebuilding the result from a clean checkout and re-measuring every pixel. Its M3 model passed three of four at the same pace as the Hyper worker (about fourteen minutes a pass) and failed one after a long attempt. As a coordinator it ran a full cycle on the third try: picked a ticket, dispatched it, verified the branch, had its own verifier confirm four claims, merged, and wrote the follow-ups. The first try ended on a judgment call and the second was killed by a bug in another run's watcher, since fixed.

Two things about the plan shape the schedule. It refuses bursts long before its quota is used, so requests now pass through a small local pacer that spaces them and retries quietly. And its weekly window is the real budget: a ticket cycle costs about 0.7% of the week, so each day may spend the weekly remainder divided by the days left, and the run stops for the day when that is gone.

## The decision

Both services now run at the same time, each with its own coordinator, and they share the ticket queue by claiming tickets. Hyper's day is its 250 credits, spent to the last few (248.8 of 250 today); MiniMax's day is its share of the week. The idea of one service's coordinator driving the other's workers stays written down but unused: M3 coordinates well enough on its own, and a fourth concurrent session on Hyper trips its hourly limit, which voided three benchmark replays this afternoon before the benchmarks learned to run alone.
