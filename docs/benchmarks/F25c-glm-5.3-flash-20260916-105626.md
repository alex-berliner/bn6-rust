# Replay F25c with opencode/glm-5.3-flash (high): FAIL

base 929affc (7fe7c1d147068823b52273ad8f3f4ac3cd19783a F25c mettaur: shockwave hit lands one frame after arrival (flight 44->45 per canon sub_80C6B64, present-at-init); mettaur 19698/1245->4265/800 at offset 203, oracle 10/10 fields 70/70. Landed by the human session as a verified partial: acceptance 0 unmet, the 8-frame departure-spray residue is F25d)
cost $0.4552, 129 turns, 45 min, thinking high, role worker

expected: {'mettaur': ('4265', '800', '70')}

```
verify_rows: wt/replay-F25c-20260916-105626 (213f9af) in /tmp/bnwt/verify-213f9af
  mettaur        FAILED   19698/1245/70/60824      MISMATCH total,worst (claimed 4265/800/70/-)
verify_rows: FAIL
```

session: /tmp/bn-pi/replay/20260916-105626

balance 1.0 -> 1.0 but 7 other pi sessions were spending: credits not attributable
