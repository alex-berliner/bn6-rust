# Sixteen free models, one archived ticket, no worker

The replay benchmark re-runs an archived ticket from its base commit with a candidate model and checks whether it reaches the verified answer. Today every tool-capable free model on OpenRouter got the same ticket (F18d, a small window-close fix) with a five-minute wall clock each, one at a time because the free tier's 1,000 requests a day are shared across all of them.

- **Two produced a passing commit**: thinkingmachines/inkling-small in one minute and nex-agi/nex-n2.5-mini in five. Re-run after the quota reset, inkling-small did nothing in 99 turns and failed a harder ticket (the shockwave-flight fix); the nex run hit the quota. One pass out of three attempts is a coin, not a worker.
- **Three returned nothing at all** (Gemma 4 26B and dots-3 rejected the requests; Nemotron 3.5 Lightning answered four times).
- **Eleven worked without finishing**: real tool calls and text, no commit in five minutes; the Ling family and Cohere's coding model ran 200 to 300 tiny turns, shaped by the 20-requests-a-minute throttle rather than by the task.
- **Nothing cached** on most of them, which for a metered model would make a 100-turn ticket ten times more expensive; free, it just made them slow.

For comparison, the paid tier's default worker (Muse Spark contributor) passes the same ticket for $0.10 in 14 minutes with 92% cache hits, and GLM 5.3 Flash fails it at $0.19.

The tool that produced this table also caught its own blind spot along the way: a branch with no commits used to count as a pass when the rows it checks were unchanged; it now reports a no-op instead. Full table in docs/benchmarks/free-models-2026-09-14.md.
