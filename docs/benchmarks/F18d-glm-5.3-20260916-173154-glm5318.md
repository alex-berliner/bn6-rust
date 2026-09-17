# Replay F18d with zai/glm-5.3 (high): PASS

base 9790ff1 (bb8e8f06596e4baac3a9589b5d7d7c0630acc923 F18d windowclose: draw gauge body on close-blank frame; BG3 k11 1596->0, total 650544->648948; verifier CONFIRMED all 3 claims)
cost $0.7187, 82 turns, 27 min, thinking high, role worker

expected: {'windowclose': ('648948', '27391', '40')}

```
verify_rows: wt/replay-F18d-20260916-173154-glm5318 (8255a97) in /tmp/bnwt/verify-8255a97
  windowclose    FAILED   648948/27391/40/732198   MATCH (isolated line)
verify_rows: PASS
```

session: /tmp/bn-pi/replay/20260916-173154-glm5318

balance 1.0 -> 1.0 but 1 other pi sessions were spending: credits not attributable
