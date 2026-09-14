# Replay F25c with openrouter/thinkingmachines/inkling-small:free (off): FAIL

base 929affc (7fe7c1d147068823b52273ad8f3f4ac3cd19783a F25c mettaur: shockwave hit lands one frame after arrival (flight 44->45 per canon sub_80C6B64, present-at-init); mettaur 19698/1245->4265/800 at offset 203, oracle 10/10 fields 70/70. Landed by the human session as a verified partial: acceptance 0 unmet, the 8-frame departure-spray residue is F25d)
cost $0.0000, 138 turns, 2 min, thinking off, role worker

expected: {'mettaur': ('4265', '800', '70')}

```
verify_rows: wt/replay-F25c-20260914-070049 (f3e8a2b) in /tmp/bnwt/verify-f3e8a2b
  mettaur        FAILED   22613/1245/70/63738      MISMATCH total,worst (claimed 4265/800/70/-)
verify_rows: FAIL
```

session: /tmp/bn-pi/replay/20260914-070049
