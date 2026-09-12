# MODEL_RESEARCH — OpenRouter model survey for the bn agent roles (2026-09-12)

Four research agents (Sonnet 5, web search) produced the reports below. They are pasted
verbatim; the synthesis and per-role picks are in the session that commissioned them and in
`SUBAGENT_FLOWS.md` once revised. Prices are from pi's cached OpenRouter catalogue
(`~/.pi/agent/models-store.json`, 375 models), dumped to the session scratchpad as
`openrouter_models.tsv`.

Evidence-quality warning that applies to everything below: most 2026 benchmark numbers came
through aggregator sites (benchlm.ai, llm-stats.com, codingfleet.com, layer3labs.io) rather
than the benchmarks' own pages; Artificial Analysis index snapshots conflict with each other
across index versions; Terminal-Bench 2.0 / 2.1 / 3.0 / 4.0 scores are not comparable; no
benchmark exists for hand-written ARM/Thumb reading or for no_std Rust. Treat every
percentage as indicative and re-check the primary source before it becomes load-bearing.

---

## Addendum, 2026-09-12 evening: what measurement changed

The picks in the session that commissioned these reports ranked models by benchmark and list price.
Two tickets later, the measured driver of cost is cache-read price x turns x context, plus whether
tool calls work through OpenRouter on a pinned first-party endpoint. Live endpoint prices (OpenRouter
API, 2026-09-12): cache read per million -- DeepSeek V4.1 Flash on DeepSeek $0.003, GPT-5.6 Luna on
OpenAI $0.01-0.02, GLM-5.3-Flash on Z.AI $0.03, Gemini 3.8 Flash $0.0375-0.075, GPT-5.6 Sol on OpenAI
$0.10, Sonnet 5 $0.20, Opus 5 $0.50, Grok 4.6 $0.50. Sol lists at $1/$5 on OpenAI's cheapest endpoint,
not the $5/$30 launch price. One identical 3-tool task, all four answers correct: GLM-5.3-Flash
$0.0011 (20 s), DeepSeek V4.1 Flash $0.0017 (7 s), Luna $0.0023 (6 s), Gemini 3.8 Flash $0.0162 (24 s,
~3.7k uncached tokens re-sent per turn). The routing that follows is in HANDOFF §13.

---

## Report 1 — closed-weight frontier models

# Frontier Closed-Weight Model Assessment for Agent-System Roles (OpenRouter, Sept 2026)

Research conducted via 27 web searches against vendor announcements, Artificial Analysis, SWE-bench/Terminal-Bench aggregators, OpenRouter model pages, and practitioner reviews. Where a number could not be found, that is stated explicitly rather than inferred.

### OpenAI: GPT-5.5 / GPT-5.5-Pro
GPT-5.5 shipped April 23–24, 2026 as OpenAI's "smartest and most intuitive" model, with ~40% fewer output tokens per Codex task than GPT-5.4 and SOTA agentic-coding/knowledge-work scores at launch ([OpenAI](https://openai.com/index/introducing-gpt-5-5/), [TechCrunch](https://techcrunch.com/2026/05/05/openai-releases-gpt-5-5-instant-a-new-default-model-for-chatgpt/)). GPT-5.5-Pro is a deep-reasoning variant with a ~1.05M-token window (922K in/128K out), priced at OpenRouter's top end ($30/$180) ([OpenRouter](https://openrouter.ai/openai/gpt-5.5-pro)). One secondary source puts GPT-5.5 at 58.6% SWE-bench Pro ([layer3labs](https://www.layer3labs.io/guides/grok-4-5-benchmarks)) — approximate, not vendor-published. No AA Intelligence Index or Terminal-Bench number for 5.5 specifically was found. Explicit prompt caching (breakpoint-based) is documented as an OpenAI feature only from GPT-5.6 onward ([AIHubMix](https://aihubmix.com/blog/gpt-5-6-is-live-prompt-caching-billing-changes-explained)).

### OpenAI: GPT-5.6 (Luna / Sol / Terra)
Previewed July 9, 2026, then GA ([VentureBeat](https://venturebeat.com/technology/openai-unveils-gpt-5-6-sol-terra-and-luna-models-but-only-accessible-to-limited-preview-partners-for-now-per-us-gov), [OpenAI Help Center](https://help.openai.com/en/articles/20001325-a-preview-of-gpt-56-sol-terra-and-luna)). The split is a capability/latency tier: **Sol** is the flagship for hardest reasoning/coding; **Terra** is "GPT-5.5-competitive" at ~2x lower cost; **Luna** is the fastest/cheapest, for summarization, routing, drafting ([OpenAI](https://openai.com/index/gpt-5-6/), [Vellum](https://www.vellum.ai/blog/gpt-5-6-sol-terra-luna-explained)). Launch pricing was Sol $5/$30, Terra $2.50/$15, Luna $1/$6; Luna was cut 80% and Terra 20% on July 30, 2026 — matching the catalogue's Luna ($0.20/$1.20) and Terra ($2/$12), but no public cut for Sol to the catalogue's $2/$10 was found: **unresolved discrepancy**. "Pro" variants are a higher-reasoning-effort tier, not a separately priced SKU. Benchmarks: Sol leads the Sept 2026 AA Intelligence Index at 58.9%, Terra at 55.0% ([BenchLM](https://benchlm.ai/benchmarks/artificialanalysis)); Sol/Codex leads Terminal-Bench 2.1 at 89.5% and TB2.0 at 91.9% ([codingfleet](https://codingfleet.com/blog/terminal-bench-leaderboard-2026/), [BenchLM](https://benchlm.ai/benchmarks/terminal-bench-2)); Sol ranks #6/152 on agentic tool-use per one aggregator ([layer3labs](https://www.layer3labs.io/guides/gpt-5-6-review)). Practitioner note: good multi-step tool-call chains, but a "tendency to fill gaps with assumptions" that compound unsupervised. Sol/Terra/Luna support explicit prompt caching via `prompt_cache_key`. No long-context needle number found for 5.6.

### OpenAI: GPT-6 Astra
Released to approved users Sept 3, GA Sept 4, 2026 ([CNBC](https://www.cnbc.com/2026/09/03/open-ai-astra-gpt-6-cyber.html), [Al Jazeera](https://www.aljazeera.com/economy/2026/9/4/openai-unveils-gpt-6-astra-amid-rising-scrutiny-and-safety)). API id `gpt-6-astra`, 1M context, priced at 2.5x Sol's launch price ([9to5Mac](https://9to5mac.com/2026/09/04/openai-releasing-major-upgrade-to-chatgpt-and-codex-with-gpt-6-astra-details-here/)). AA's own article claims Astra ties Fable 5.1 for the top Intelligence/Coding-Agent Index spot at ~40–60% of Fable's cost ([Artificial Analysis](https://artificialanalysis.ai/articles/artificial-analysis-intelligence-index-v4-1-1)); a Sept 10 aggregator table ranks it 5th at 52.8% ([BenchLM](https://benchlm.ai/benchmarks/artificialanalysis)) — unresolved conflict, likely index-version churn. Week-1 practitioner reports: verbose by default; a security classifier hard-blocks exploit-generation requests; under-actions tentative phrasing ([layer3labs](https://www.layer3labs.io/guides/gpt-6-astra-user-reports), [stationx](https://app.stationx.net/articles/gpt-6-astra-security)). No independent SWE-bench/Terminal-Bench/Aider number yet.

### OpenAI: GPT-5.4 family and GPT-5.3-Codex
GPT-5.3-Codex (Feb 5, 2026) was SOTA on SWE-bench Pro and Terminal-Bench 2.0 at release, OSWorld-Verified 64% ([OpenAI](https://openai.com/index/introducing-gpt-5-3-codex/)). GPT-5.4: OSWorld 75%, GDPval 83%, SWE-bench Pro 57.7%, SWE-bench Verified ~80%, Toolathlon 54.6% ([OpenAI Devs on X](https://x.com/OpenAIDevs/status/2029620996962242663)). GPT-5.4-mini ($0.75/$4.5, 400K) and GPT-5.4-nano ($0.20/$1.25, 400K) have no independent benchmark scores surfaced ([OpenRouter](https://openrouter.ai/openai/gpt-5.4-mini), [OpenRouter](https://openrouter.ai/openai/gpt-5.4-nano)). Explicit caching is GPT-5.6+ only; this family relies on automatic caching.

### Google: Gemini 3.1 Pro / 3.x Flash line / 3.5 Flash-Lite
Gemini 3.1 Pro (preview, Feb 2026): ARC-AGI-2 77.1%, GPQA Diamond 94.3% ([Google Blog](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-pro/), [MarkTechPost](https://www.marktechpost.com/2026/02/19/google-ai-releases-gemini-3-1-pro-with-1-million-token-context-and-77-1-percent-arc-agi-2-reasoning-for-ai-agents/)). Sonnet 5's system card cites Gemini 3.1 Pro at 80.6% SWE-bench Verified. Flash line: 3.5 Flash (May 19), 3.6 Flash (Jul 21, with 3.5 Flash-Lite), 3.7 Flash (Aug 13, TB2.1 81.6%), 3.8 Flash (Sept 2, TB2.1 90.8%, HLE-Verified 54.9%) ([Google Blog](https://blog.google/innovation-and-ai/models-and-research/gemini-models/3-8-flash-and-3-8-flash-cyber/), [Vellum](https://www.vellum.ai/blog/gemini-3-8-flash-benchmarks-explained)); 3.8 Flash pricing is locked at $0.75/$3.75 through end-2026, doubling Jan 1 2027. **Gemini 3.5 Flash-Lite** ($0.30/$2.50): AA Index 23, SWE-bench Pro 54.2%, OSWorld-Verified 74.0% ([Artificial Analysis](https://artificialanalysis.ai/models/gemini-3-5-flash-lite)). **Long-context**: Gemini 3 Deep Think reported as the only frontier family holding ~99% single-needle / 89% multi-needle NIAH at 1M and >80% RULER at 256K ([digitalapplied.com](https://www.digitalapplied.com/blog/long-context-retrieval-needle-in-haystack-2026)) — Deep Think, not confirmed for 3.1 Pro or Flash. Caching: implicit on Gemini 3.x, 0.25x read cost; OpenRouter historically required a per-provider "prompt caching" toggle for Gemini.

### xAI: Grok 4.3 / 4.5 / 4.6 / Grok Build 0.1
Grok 4.3 (April 2026, 1M context, $1.25/$2.50): AA Index 53, comparatively low hallucination ([VentureBeat](https://venturebeat.com/technology/xai-launches-grok-4-3-at-an-aggressively-low-price-and-a-new-fast-powerful-voice-cloning-suite)). Grok 4.5 (July 8, 2026): SWE-bench Pro 64.7%, SWE Marathon 29.0%, Terminal-Bench 2.1 83.3% ([cryptobriefing](https://cryptobriefing.com/grok-4-5-swe-marathon-benchmark/), [HokAI](https://hokai.io/hub/models/grok-4.5)) — but AA-Omniscience hallucination rate reportedly **rose from 25% (4.3) to 54% (4.5)** ([layer3labs](https://www.layer3labs.io/guides/grok-4-5-review)). Grok 4.6 (Aug 12, 2026, 500K context, $2/$6): AA Index 61 per one source ([basenor](https://www.basenor.com/blogs/news/xai-launches-grok-4-6-1753-elo-half-the-price-of-rival-frontier-models)) but 44.4 in the Sept 10 BenchLM table — conflict; DeepSWE v1.1 65.9%, CursorBench v3.2 69.9% ([datanorth.ai](https://datanorth.ai/news/xai-releases-grok-4-6), [kie.ai](https://kie.ai/blog/grok-4-6-release-analysis)). Grok Build 0.1 ($1/$2, 256K) is xAI's agentic-coding CLI model, early access ([basenor](https://www.basenor.com/blogs/news/xai-launches-grok-build-beta-agentic-coding-cli-explained), [OpenRouter](https://openrouter.ai/x-ai/grok-build-0.1)). No LiveCodeBench, Aider, or long-context numbers for any Grok. Caching automatic at 0.25x.

### Anthropic: Opus 5 / Sonnet 5 / Haiku 4.5 / Fable 5.1
**Opus 5** (July 24, 2026, $5/$25): SWE-bench Verified 96.0% (saturated; within ~1pt of Mythos 5 / Fable 5), SWE-bench Pro 79.2%, OSWorld 2.0 70.57%, ARC-AGI-3 30.2% ([datanorth.ai](https://datanorth.ai/news/claude-opus-5-by-anthropic), [sitepoint](https://www.sitepoint.com/claude-opus-5-performance/)). Practitioner complaints: verbosity, over-cautious confirmation-seeking, over-engineering of simple tasks, a documented higher hallucination rate, slow first token at max effort ([explainx.ai](https://www.explainx.ai/blog/opus-5-over-engineering-reddit-reaction-august-2026), [emergent.sh](https://emergent.sh/learn/claude-opus-5-reviews)). **Sonnet 5** (June 30, 2026, $2/$10): SWE-bench Verified 82.1%, Terminal-bench 76.1%, GPQA Diamond 96.2%, OSWorld-Verified 88.3% ([siliconreport](https://www.siliconreport.com/anthropics-claude-sonnet-5-breaks-80-on-swe-bench-verified-widens-benchmarks-over-competit-220e6417)). Weaknesses: occasional refusals on legitimate security work; verbalizes internal instructions; over-literal adherence to review-scoping instructions reduces recall in code review ([neuraltrust.ai](https://neuraltrust.ai/blog/claude-sonnet-5-security-safety-system-card), [thehumanco.org](https://thehumanco.org/ai-resources/claude-sonnet-5-in-practice)). **Haiku 4.5** (Oct 15, 2025 — oldest in set), 200K context, $1/$5, SWE-bench Verified 73.3%, AA Index 15.4 ([anthropic.com](https://www.anthropic.com/claude/haiku), [OpenRouter](https://openrouter.ai/anthropic/claude-haiku-4.5)); documented repetitive tool-call loop failure ([GitHub issue #10029](https://github.com/anthropics/claude-code/issues/10029)). **Fable 5.1** (Sept 1, 2026, $10/$50, cache reads $0.25/M): GDPval-AA v2 1853, Terminal-Bench-Science 52.6%, browser-agent 82% ([anthropic.com](https://www.anthropic.com/claude-fable-and-mythos-5-1), [officechai](https://officechai.com/ai/fable-5-1-benchmarks/)); SWE-bench Pro 81.2% ([BenchLM](https://benchlm.ai/benchmarks/swePro)). Practitioner notes: expensive, slower, very verbose. All four use explicit `cache_control` at ~0.1x read cost.

### Cross-cutting
Aider Polyglot: no 2026 frontier entries found. LiveCodeBench: not found for GPT/Claude/Grok. Terminal-Bench 4.0 (Sept 2026) is not comparable to 2.x.

| Model | Price in/out | Best coding score | Reasoning | Long-context | Caveats |
|---|---|---|---|---|---|
| gpt-5.5 | 5/30 | ~58.6% SWE-bench Pro (secondary) | not found | not found | superseded; automatic caching only |
| gpt-5.5-pro | 30/180 | not found | not found | 922K/128K | most expensive |
| gpt-5.6-luna | 0.20/1.20 | not found | AA 51.2 | not found | assumptions compound unsupervised |
| gpt-5.6-sol | 2/10 catalogue vs 5/30 announced | TB2.1 89.5%, TB2.0 91.9% | AA 58.9 (top) | not found | price discrepancy unresolved |
| gpt-5.6-terra | 2/12 | not found | AA 55.0 | not found | "5.5-competitive at 2x lower cost" |
| gpt-6-astra | 10/50 | claimed SOTA, unverified | AA 52.8–~53 (conflict) | 1M | 1 week old; exploit-gen hard-blocked |
| gpt-5.4 | 2.5/15 | SWE Pro 57.7%, Verified ~80% | not found | not found | |
| gpt-5.4-mini / nano | 0.75/4.5 · 0.2/1.25 | not found | not found | 400K | no independent benchmark |
| gemini-3.1-pro-preview | 2/12 | SWE Verified 80.6% | ARC-AGI-2 77.1% | strong (family; Deep Think confirmed) | |
| gemini-3.5-flash | 1.5/9 | not found | AA 50.2 | not found | |
| gemini-3.8-flash | 0.75/3.75 | TB2.1 90.8% | HLE-V 54.9% | not found | price doubles Jan 2027 |
| gemini-3.5-flash-lite | 0.3/2.5 | SWE Pro 54.2% | AA 23 | not found | strong cheap tier |
| grok-4.5 | 2/6 | SWE Pro 64.7%, TB2.1 83.3% | not found | not found | hallucination 25%→54% |
| grok-4.6 | 2/6 | DeepSWE 65.9% | AA 44.4–61 (conflict) | not found | |
| grok-4.3 | 1.25/2.5 | not found | AA 53 | not found | low hallucination |
| grok-build-0.1 | 1/2 | not found | not found | 256K | early access |
| claude-opus-5 | 5/25 | SWE Verified 96.0%, Pro 79.2% | ARC-AGI-3 30.2% | 1M | verbose, over-engineers, hallucination reports |
| claude-sonnet-5 | 2/10 | SWE Verified 82.1%, TB 76.1% | GPQA 96.2% | not found | review recall quirk; security refusals |
| claude-haiku-4.5 | 1/5 | SWE Verified 73.3% | AA 15.4 | 200K only | tool-call loops |
| claude-fable-5.1 | 10/50 | SWE Pro 81.2% | AA 53.4 (conflict) | not found | expensive, slow, verbose |

---

## Report 2 — open-weight and Chinese-lab models

All figures are "vendor-reported" or "independent/tracked" as labelled. Kimi K2.7-Code, K3, GLM-5.3, DeepSeek V4.1-Flash have **no independent SWE-bench Verified / Aider numbers yet**.

### DeepSeek
V4-Pro/Flash shipped April 24, 2026 ([morphllm](https://www.morphllm.com/deepseek-v4), [yottalabs](https://www.yottalabs.ai/post/deepseek-v4-release-date-specs-how-to-access-2026)); V4-Pro is 1.6T/49B-active MoE, 1M context, ~$0.80/$1.60 ([OpenRouter](https://openrouter.ai/deepseek/deepseek-v4-pro)). V4-Flash 284B/13B, ~$0.07/$0.13. V4.1-Flash (~Sep 10, 2026): 4-bit KV redesign, vendor Terminal-Bench 2.1 90.6, DeepSWE 74.2% ([SiliconANGLE](https://siliconangle.com/2026/09/10/deepseek-releases-v4-1-flash-says-it-outperforms-flagship-v4-pro/)) — **unreproduced**. V4-Pro-Max: 80.6% SWE-bench Verified, 67.9% TB2.0, 55.4% SWE Pro (llm-stats, June 2026; [DataCamp](https://www.datacamp.com/blog/deepseek-v4)). AA Index ~36–43.8 depending on snapshot ([x.com/ArtificialAnlys](https://x.com/ArtificialAnlys/status/2097025645889069094)). **Quantization**: V4-Flash ships ~96% of routed experts in MXFP4; OpenRouter providers fp8-quantize activations on top; declared precision does not predict quality; Morph reported as the one true-bf16 provider ([mmoustafa.com](https://mmoustafa.com/blog/so-you-want-to-use-openrouter/)). Cache reads 0.1x.

### Qwen
Qwen3.8-Max (2.4T/95B active) ~Aug 3, 2026 ([MarkTechPost](https://www.marktechpost.com/2026/08/03/alibaba-qwen-releases-qwen3-8-max/)); vendor: TB2.1 86.6, IFBench 82.8 ([officechai](https://officechai.com/ai/alibaba-releases-qwen-3-8-max-beats-gpt-5-6-sol-and-fable-on-many-benchmarks/)). AA Index 40. Qwen3.7-Max (May 21, 2026): AA Intelligence 46.0, Coding 66.0 ([Artificial Analysis](https://artificialanalysis.ai/models/qwen3-7-max)); Qwen3.7-Plus AA 32. Qwen3.8-27B / Flash: 1M context, cheap ([OpenRouter](https://openrouter.ai/qwen/qwen3.8-27b)). Aider: older Qwen3-Coder-480B ~61–62%; Qwen3.6-35B-A3B 78.67% ([aider.chat](https://aider.chat/2025/05/08/qwen3.html)); nothing for 3.8. Caching: explicit cache_control at 0.1x ([OpenRouter blog](https://openrouter.ai/blog/tutorials/prompt-caching-sticky-routing/)).

### Moonshot (Kimi)
Kimi K3 (2.8T/104B active, 1M context) July 16, 2026 ([Tom's Hardware](https://www.tomshardware.com/tech-industry/artificial-intelligence/moonshot-releases-2-8-trillion-parameter-kimi-k3)): FrontierSWE 81.2, TB2.1 88.3 (independently tracked; [codingfleet](https://codingfleet.com/blog/terminal-bench-leaderboard-2026/)), AA 43.8–44. Moonshot itself says K3 trails Claude and Sol ([nxcode](https://www.nxcode.io/resources/news/kimi-k3-benchmarks-coding-agent-evaluation-guide-2026)). K2.7-Code (June 12): only Moonshot's proprietary suites ([MarkTechPost](https://www.marktechpost.com/2026/06/12/moonshot-ai-releases-kimi-k2-7-code-a-coding-model-reporting-21-8-on-kimi-code-bench-v2-over-k2-6/)). K2.6: SWE Pro 58.6% ([designforonline](https://designforonline.com/ai-models/moonshotai-kimi-k2-6/)). **Practitioner weaknesses**: tool-selection confusion under many-tool schemas, degenerate retry loops, hallucinated calls to tools not in the request — Moonshot's hosted API runs a constrained-decoding "Enforcer" to suppress it ([trilogyai](https://trilogyai.substack.com/p/taming-tool-calling-with-kimi-k25), [vLLM blog](https://vllm.ai/blog/2025-10-28-kimi-k2-accuracy)). Caching 0.25x.

### Z.ai (GLM)
GLM-5.3 (Aug 14, 2026, 743B/40B): TB3.0 4.6→28.3, TB2.1 88.2% (codingfleet), Z.ai Code Bench 31.4% vs Opus 4.8's 29.5% at ~40% fewer tokens ([the-decoder](https://the-decoder.com/zhipu-ai-releases-glm-5-3-claims-its-the-strongest-open-weights-coding-model/)); headline gains are Zhipu-internal ([artificialintelligence-news](https://www.artificialintelligence-news.com/news/zhipu-glm-5-3-benchmarks-explained/)). AA: GLM-5.3 and K3 co-lead open models at 44; GLM-5.3-Flash 41.9–42. GLM-5.2 (June 17, MIT, 1M): TB2.1 81.0, SWE Pro 62.1 ([labellerr](https://www.labellerr.com/blog/glm-5-2-open-weight-ai-model/)). **25 OpenRouter providers**; Exacto routing targets tool-call accuracy ([OpenRouter](https://openrouter.ai/z-ai/glm-5.3)). Cached ~75% discount.

### MiniMax
M3 (May 31, 2026, 1M): SWE Pro 59.0%, $0.23–0.30/$0.96–1.20 ([VentureBeat](https://venturebeat.com/technology/minimax-m3-debuts-eclipsing-gpt-5-5-and-gemini-3-1-pro-on-key-benchmark-performance-for-just-5-10-of-the-cost)). M2.7 (Mar 18, 204,800 context): SWE Pro 56.2%, TB2 57.0 ([digitalapplied](https://www.digitalapplied.com/blog/minimax-m2-7-agentic-coding-release-guide)).

### Others
Tencent Hy4-preview (Aug 28, 770B/49B, Apache 2.0): TB2.1 85.4, DeepSWE 64.3, $0.83/$2.50 ([mindstudio](https://www.mindstudio.ai/blog/tencent-hy4-preview-benchmarks)). Xiaomi MiMo-V2.5-Pro: AA Index only 26 despite vendor claims ([Artificial Analysis](https://artificialanalysis.ai/models/mimo-v2-5-pro)). StepFun Step-3.7-Flash (May 28, 198B/11B): SWE Pro 56.26%, TB2.1 59.55% ([MarkTechPost](https://www.marktechpost.com/2026/05/29/stepfun-releases-step-3-7-flash-a-198b-moe-vision-language-model-for-coding-agents-and-search-workflows/)). Nvidia Nemotron-3-Ultra-550B (June 4): RULER 94.7% at 1M — best long-context evidence in the set — GPQA 87.0%, coding trails frontier by ~13 pts ([research.nvidia.com](https://research.nvidia.com/labs/nemotron/Nemotron-3-Ultra/)). Devstral-2512: #73/157 on one index, 99% harness reliability ([benchable.ai](https://benchable.ai/models/mistralai/devstral-2512)). gpt-oss-120b ($0.04/$0.17): ~62% SWE Verified, contested LiveCodeBench; Harmony-format tool-call leakage after ~5 chained calls ([LangChain forum](https://forum.langchain.com/t/harmony-response-format-sometimes-outputted-when-using-gpt-oss-120b-as-an-agent/2554)).

### Cross-cutting: provider/quantization risk
Identical model ids return different quality depending on provider; declared quantization is a poor proxy; pin with `provider.order` / `only`, filter with `provider.quantizations`, or use `:exacto` ([OpenRouter docs](https://openrouter.ai/docs/guides/routing/provider-selection)).

| Model | Price | Best coding score | Reasoning | Long-context | Provider caveat |
|---|---|---|---|---|---|
| deepseek-v4-pro | 0.80/1.60 | 80.6% SWE Verified (tracker) | AA ~36–43.8 | 1M, no RULER | fp8-on-fp4; Morph = bf16 |
| deepseek-v4-flash / v4.1-flash | 0.07/0.13 · 0.15/0.6 | v4.1 TB2.1 90.6 (vendor) | — | 1M | same |
| qwen3.8-max | 2/6 | TB2.1 86.6 (vendor) | AA 40 | 1M | multi-provider |
| qwen3.7-max / plus | 1.48/4.43 · 0.32/1.28 | AA Coding 66.0 (max) | AA 46 / 32 | 1M | — |
| qwen3.8-27b / flash | 0.15–0.42 / 0.47–3 | not found | not found | 1M | cheap tier |
| kimi-k3 | 2.34/11.7 | TB2.1 88.3% (independent) | AA 44 | 1M | tool-call hallucination |
| kimi-k2.7-code | 0.71/3.5 | vendor suites only | — | 256K | same |
| glm-5.3 | 1.4/4.4 | TB2.1 88.2% (independent) | AA 44 | 1M | 25 providers; vendor claims |
| glm-5.3-flash | 0.15/0.5 | slightly below 5.3 | AA 42 | 1M | pin provider |
| glm-5.2 | 0.97/3.04 | SWE Pro 62.1% | — | 1M | — |
| minimax-m3 | 0.3/1.2 | SWE Pro 59.0% | — | 1M | — |
| minimax-m2.7 | 0.3/1.2 | SWE Pro 56.2%, TB2 57.0 | — | 205K | — |
| tencent hy4-preview | 0.83/2.5 | TB2.1 85.4 | — | 1M | native FP8 |
| xiaomi mimo-v2.5-pro | 0.44/0.87 | vendor claims | AA 26 | 1M | vendor-claim gap |
| stepfun step-3.7-flash | 0.2/1.15 | SWE Pro 56.26% | — | 262K | — |
| nvidia nemotron-3-ultra | 0.63/3.13 | trails by ~13 pts | GPQA 87.0 | RULER 94.7% @1M | reader, not coder |
| devstral-2512 | — | #73/157; 99% reliability | — | 256K | — |
| gpt-oss-120b | 0.04/0.17 | ~62% SWE Verified | — | — | tool-call leakage |

---

## Report 3 — task-specific evidence (assembly, long context, faithfulness, review, Rust)

### Assembly / reverse engineering
No benchmark targets hand-written ARM/Thumb. Adjacent: **BinMetric** (IJCAI 2025, [arxiv 2505.07360](https://arxiv.org/pdf/2505.07360)), **REBench** ([arxiv 2604.27319](https://arxiv.org/html/2604.27319v1)). A deobfuscation study found **DeepSeek-R1 architecture-robust, 72.31% semantic preservation on ARM**, while CodeLlama is CISC-biased ([arxiv 2604.08083](https://arxiv.org/html/2604.08083v1)) — the one concrete ARM data point. **REFORGE** ([arxiv 2607.07738](https://arxiv.org/abs/2607.07738)): RE accuracy is fragile to optimisation level and alignment. **OASIF** ([arxiv 2606.29155](https://arxiv.org/pdf/2606.29155)) compares GPT-5, Sonnet 4.5, Opus 4.6, Gemini 2.5 Pro on assembly instruction-following; no ranked table surfaced. **DecompileBench** ([arxiv 2505.11340](https://arxiv.org/abs/2505.11340)): LLM decompilation beats commercial tools on readability but has 52.2% lower functional correctness — a narrative explanation of asm is not a mechanical claim.

### Long-context reading
**Context Rot** (Chroma, [trychroma.com](https://trychroma.com/research/context-rot)): all 18 frontier models degrade with length; coherent long documents did worse than shuffled ones. **RULER**: universal degradation. **NoLiMa** ([arxiv 2502.05167](https://arxiv.org/abs/2502.05167)): the rigorous test; leaderboard updated 2026-05-24. **Fiction.LiveBench** (Aug 2026): Grok 4 and Gemini standouts above 192K. **LongBench v2** (June 2026, llm-stats): Qwen3.8 Max 66.3% > Opus 4.5 64.4% > Qwen3.5-397B 63.2% — the benchmarks disagree on the winner.

### Faithful reporting / hallucination
**Vectara Hallucination Leaderboard** ([github](https://github.com/vectara/hallucination-leaderboard), HHEM-2.3, Feb 2026): finix_s1_32b 1.8%, **gpt-5.4-nano 3.1%** — the one named cheap model with a documented low rate. No data for gemini-3.8-flash, 3.5-flash-lite, haiku-4.5, deepseek-v4-flash, qwen3.8-flash, glm-5.3-flash, minimax-m3, luna. **IFBench**: Qwen3.8 Max 0.828 leads; GLM-5 best open IFEval. "Abstraction bias" ([arxiv 2508.17361](https://arxiv.org/html/2508.17361v2)): models over-generalise familiar patterns and miss odd literals — relevant to a measurer transcribing an unexpected number.

### Agentic tool use of cheap models
BFCL ([gorilla](https://gorilla.cs.berkeley.edu/leaderboard.html)) fetched only as a paraphrase; **AgentFloor** ([arxiv 2605.00334](https://arxiv.org/pdf/2605.00334)) is on-topic, scores not surfaced. τ²-Bench: Fable 5 leads Airline 81.5%; Step-3.5-Flash leads broader tau-bench 88.2%. **GLM-5.3-Flash 84.3% on TB2.1** (codingfleet) — the only cheap model from the list with an agentic-CLI number.

### Code review / verification
**"Bigger Isn't Always Better"** ([arxiv 2606.15689](https://arxiv.org/html/2606.15689)): on 150 review samples, **Haiku 4.5 beat Sonnet 4.6** (F1 0.365 vs 0.343, +18% recall, 3.2x cheaper); catastrophic synthetic-to-real collapse (F1 0.847 → 0.066); **diff size dominates** (F1 0.66–0.80 under 10 lines → 0.04–0.07 over 150). Cross-family: multi-LLM cross-review anecdote ([sosuke.com](https://sosuke.com)); **Gemini tends to false-accept, GPT-4o to false-reject** ([arxiv 2411.01414](https://arxiv.org/pdf/2411.01414) lineage).

### Rust
Aider Polyglot is the only Rust breakdown: **Opus 4.8 beats Gemini 3.5 Pro on Rust and C++ by 6–7 points** (June 2026, contracollective.com); Rust is the weakest language for every model. **No benchmark isolates no_std/embedded Rust.**

---

## Report 4 — OpenRouter mechanics (caching, routing, pi)

### Prompt caching ([docs](https://openrouter.ai/docs/features/prompt-caching))
Anthropic: explicit `cache_control`, min 1,024–4,096 tokens, TTL 5 min / 1 h opt-in, reads 0.1x, writes 1.25x / 2x. OpenAI: automatic, min 1,024, reads 0.25–0.5x, GPT-5.6+ writes 1.25x, 30-min TTL (pi 0.85.1 fixed `prompt_cache_options.ttl: "30m"`). Gemini: implicit on 2.5+, min 1,024 (Flash) / 4,096 (Pro), TTL ~3–5 min, reads 0.25x. DeepSeek: automatic, reads 0.1x. Moonshot: automatic, 0.25x. xAI: automatic, 0.25x. Qwen: explicit `cache_control` required, 0.1x. Z.AI: automatic, ~0.2x. MiniMax: not documented.

### Provider routing ([docs](https://openrouter.ai/docs/features/provider-routing))
Default is load-balanced and price-weighted; **provider can change between requests, silently breaking caching**. Pin: `provider.order: ["slug"]` + `provider.allow_fallbacks: false`. Quantization filter: `provider.quantizations: ["fp8"]` etc. For any open-weight model in a long-lived conversation, pin the provider.

### Rankings
[openrouter.ai/rankings](https://openrouter.ai/rankings) measures adoption, not quality; live table not fetchable. **State of AI** ([openrouter.ai/state-of-ai](https://openrouter.ai/state-of-ai), [arxiv 2601.10088](https://arxiv.org/abs/2601.10088)): Claude >60% of programming spend for most of the period; Google ~15%; OpenAI 2%→8%; MiniMax, Z.AI, Qwen gaining. Aggregator claims ("MiMo leads programming at 19.1%") unverified and from low-quality sources.

### Reliability and tool-calling breakage
Kimi K2 via OpenRouter: tool calls failing ([zed #37032](https://github.com/zed-industries/zed/discussions/37032), [zed #34761](https://github.com/zed-industries/zed/issues/34761), [opencode #8851](https://github.com/anomalyco/opencode/issues/8851)). MiniMax on OpenRouter in pi: [pi #5229](https://github.com/earendil-works/pi/issues/5229) (2026-05-30) HTTP 400 "unknown variant `developer`" — status unresolved at fetch. OpenRouter's Exacto announcement concedes ~8% average tool-call error for GLM before Exacto, ~1% after.

### pi 0.85.x
Anthropic-via-OpenRouter `cache_control`: fixed after [pi #583](https://github.com/earendil-works/pi/issues/583); `maybeAddOpenRouterAnthropicCacheControl`, `cacheControlFormat` ("anthropic" / "alibaba"). Usage JSON has `cacheRead` / `cacheWrite`; bugs: [pi #6469](https://github.com/earendil-works/pi/issues/6469) GPT-5.6 cache writes reported zero; [pi #8075](https://github.com/earendil-works/pi/issues/8075) Kimi `cached_tokens` untracked.

### Cost control
Usage accounting is always-on in responses (`cached_tokens`, `cache_write_tokens`, `cost`) ([docs](https://openrouter.ai/docs/cookbook/administration/usage-accounting)). `provider.max_price` caps price per request. `:batch` variants exist (cheaper, async). `:exacto` ([docs](https://openrouter.ai/docs/guides/routing/model-variants/exacto)) sorts providers by tool-calling quality; "Auto Exacto" applies it by default for tool-calling requests.
