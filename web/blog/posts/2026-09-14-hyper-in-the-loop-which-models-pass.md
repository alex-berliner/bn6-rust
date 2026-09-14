# Hyper in the loop: which models pass

The project moved its day-to-day compute to Charm Hyper today: a flat subscription of 250 credits a day, to be used in full every day, with OpenRouter kept as a reserve that nothing touches by default. Before any role changed model, the replay benchmark re-ran two archived tickets from their base commits on Hyper's models: a small window-close fix (F18d) and a mechanism fix (the shockwave's one-frame hit delay, F25c). Pass means the model reproduced the verified landing, checked from a clean checkout.

| model | small fix | mechanism fix |
|---|---|---|
| GLM 5.3 Flash | pass, $0.33, 16 min | pass, $0.42, 13 min |
| Qwen 3.8 Flash | pass, $0.42, 37 min | pass, $0.62, 53 min |
| MiniMax M3 | pass, $1.34, 13 min | pass, $0.73, 6 min |
| Kimi K2.5 | pass, $1.36, 16 min | fail, $1.66 |
| DeepSeek 4.1 Flash | no commit, $0.69 | not run |

GLM 5.3 Flash takes the worker role: cheapest passer on both, fast, with cache hits above 90% through Hyper's gateway. The verifier moves to Qwen so it is not checking its own family's work; the coordinator runs on Qwen too. On the free tier the same models had looked hopeless, because that tier's hourly request limit cut every run short; under the plan there were no rate-limit errors at all.

For scale: the previous worker (Muse on OpenRouter) did the small fix for $0.10, so Hyper's per-token prices are about three times higher, but inside the daily allocation the marginal cost is zero, and 250 credits buys roughly 28 to 35 landings a day at GLM's rate, which is about what the machine can verify. The loop now runs on Hyper only, stops itself when the day's credits are gone, and restarts on a timer after the refresh. Today's first Hyper-only landing was the script VMs.
