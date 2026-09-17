# Replay F25c with hyper/glm-5.3-flash (high): PASS

base 929affc (7fe7c1d147068823b52273ad8f3f4ac3cd19783a F25c mettaur: shockwave hit lands one frame after arrival (flight 44->45 per canon sub_80C6B64, present-at-init); mettaur 19698/1245->4265/800 at offset 203, oracle 10/10 fields 70/70. Landed by the human session as a verified partial: acceptance 0 unmet, the 8-frame departure-spray residue is F25d)
cost $0.4379, 137 turns, 20 min, thinking high, role worker, variant csrc2

expected: {'mettaur': ('4265', '800', '70')}

```
verify_rows: wt/replay-F25c-20260916-223917-glm53fla1 (ea5de5e) in /tmp/bnwt/verify-ea5de5e
  mettaur        FAILED   4265/800/70/45788        MATCH (isolated line)
verify_rows: PASS
```

session: /tmp/bn-pi/replay/20260916-223917-glm53fla1

balance 82.5 -> 72.5 but 1 other pi sessions were spending: credits not attributable
