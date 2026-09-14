# Charm Hyper replays of F18d (worker role, 40 min each)

- hyper/qwen3.8-flash: NO-OP (no commits on the branch; nothing to verify)  $0.3887  277 turns  40 min  -> /home/box/Code/bn/docs/benchmarks/F18d-qwen3.8-flash-20260914-092002.md [277 turns, cache 95%]
- hyper/glm-5.3-flash: NO-OP (no commits on the branch; nothing to verify)  $0.0546  102 turns  4 min  -> /home/box/Code/bn/docs/benchmarks/F18d-glm-5.3-flash-20260914-100003.md [102 turns, cache 85%]
- hyper/deepseek-v4.1-flash: NO-OP (no commits on the branch; nothing to verify)  $0.0000  12 turns  1 min  -> /home/box/Code/bn/docs/benchmarks/F18d-deepseek-v4.1-flash-20260914-100339.md [12 turns, cache 0%]
hyper done 10:04

## Qwen 3.8 Flash again with a 75-minute clock (it had found the mechanism at 40)

- hyper/qwen3.8-flash (75 min): NO-OP (no commits on the branch; nothing to verify)  $0.0000  12 turns  0 min  -> /home/box/Code/bn/docs/benchmarks/F18d-qwen3.8-flash-20260914-100438.md
hyper2 done 10:05

## Free-tier reruns paced around the hourly rate limit


## Under the subscription (10:14): F18d, 60 min each

- hyper/qwen3.8-flash: PASS  $0.4153  297 turns  37 min  -> /home/box/Code/bn/docs/benchmarks/F18d-qwen3.8-flash-20260914-101430.md [297 turns, cache 95%; rate-limit errors 0]
- hyper/deepseek-v4.1-flash: NO-OP (no commits on the branch; nothing to verify)  $0.6894  130 turns  9 min  -> /home/box/Code/bn/docs/benchmarks/F18d-deepseek-v4.1-flash-20260914-105207.md [130 turns, cache 95%; rate-li
- hyper/glm-5.3-flash: PASS  $0.3277  240 turns  16 min  -> /home/box/Code/bn/docs/benchmarks/F18d-glm-5.3-flash-20260914-110105.md [240 turns, cache 91%; rate-limit errors 0]
- hyper/minimax-m3: PASS  $1.3355  354 turns  13 min  -> /home/box/Code/bn/docs/benchmarks/F18d-minimax-m3-20260914-111701.md [354 turns, cache 93%; rate-limit errors 0]
- hyper/kimi-k2.5: PASS  $1.3638  228 turns  16 min  -> /home/box/Code/bn/docs/benchmarks/F18d-kimi-k2.5-20260914-112944.md [228 turns, cache 92%; rate-limit errors 0]

## Passers on F12 (vdoll) and F25c (shockwave flight), 60 min each

- hyper/qwen3.8-flash on F12: 
- hyper/qwen3.8-flash on F25c: PASS  $0.6191  402 turns  53 min  -> /home/box/Code/bn/docs/benchmarks/F25c-qwen3.8-flash-20260914-114548.md
- hyper/glm-5.3-flash on F12: 
- hyper/glm-5.3-flash on F25c: PASS  $0.4180  228 turns  13 min  -> /home/box/Code/bn/docs/benchmarks/F25c-glm-5.3-flash-20260914-123914.md
- hyper/minimax-m3 on F12: 
- hyper/minimax-m3 on F25c: PASS  $0.7297  276 turns  6 min  -> /home/box/Code/bn/docs/benchmarks/F25c-minimax-m3-20260914-125223.md
- hyper/kimi-k2.5 on F12: 
- hyper/kimi-k2.5 on F25c: FAIL  $1.6573  255 turns  16 min  -> /home/box/Code/bn/docs/benchmarks/F25c-kimi-k2.5-20260914-125813.md
credits remaining: {'hypercredits': 116.00459822399999}
hypersub done 13:14
