# Replay F25c with hyper/glm-5.3-flash (high): PASS

base 929affc (7fe7c1d147068823b52273ad8f3f4ac3cd19783a F25c mettaur: shockwave hit lands one frame after arrival (flight 44->45 per canon sub_80C6B64, present-at-init); mettaur 19698/1245->4265/800 at offset 203, oracle 10/10 fields 70/70. Landed by the human session as a verified partial: acceptance 0 unmet, the 8-frame departure-spray residue is F25d)
cost $0.2090, 76 turns, 13 min, thinking high, role worker

expected: {'mettaur': ('4265', '800', '70')}

```
verify_rows: wt/replay-F25c-20260914-123914 (f072a3e) in /tmp/bnwt/verify-f072a3e
  mettaur        FAILED   4265/800/70/45788        MATCH
verify_rows: PASS
```

session: /tmp/bn-pi/replay/20260914-123914
