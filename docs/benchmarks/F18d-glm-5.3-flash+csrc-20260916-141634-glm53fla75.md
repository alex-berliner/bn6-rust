# Replay F18d with hyper/glm-5.3-flash (high): PASS

base 9790ff1 (bb8e8f06596e4baac3a9589b5d7d7c0630acc923 F18d windowclose: draw gauge body on close-blank frame; BG3 k11 1596->0, total 650544->648948; verifier CONFIRMED all 3 claims)
cost $0.2076, 108 turns, 27 min, thinking high, role worker, variant csrc

expected: {'windowclose': ('648948', '27391', '40')}

```
verify_rows: wt/replay-F18d-20260916-141634-glm53fla75 (ec6d44c) in /tmp/bnwt/verify-ec6d44c
  windowclose    FAILED   648948/27391/40/732198   MATCH (isolated line)
verify_rows: PASS
```

session: /tmp/bn-pi/replay/20260916-141634-glm53fla75

balance 195.9 -> 191.2 but 1 other pi sessions were spending: credits not attributable
