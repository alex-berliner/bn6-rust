# Replay F18d with hyper/qwen3.8-flash (high): PASS

base 9790ff1 (bb8e8f06596e4baac3a9589b5d7d7c0630acc923 F18d windowclose: draw gauge body on close-blank frame; BG3 k11 1596->0, total 650544->648948; verifier CONFIRMED all 3 claims)
cost $0.4153, 297 turns, 37 min, thinking high, role worker

expected: {'windowclose': ('648948', '27391', '40')}

```
verify_rows: wt/replay-F18d-20260914-101430 (f483555) in /tmp/bnwt/verify-f483555
  windowclose    FAILED   648948/27391/40/732198   MATCH
verify_rows: PASS
```

session: /tmp/bn-pi/replay/20260914-101430
