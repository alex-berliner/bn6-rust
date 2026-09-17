# Replay F27b with opencode/glm-5.3-flash (high): PASS

base 9d07a63 (858acb2b470ab9ad4853790668de8cc23b9a79e3 F27b popup: emotion window on canon's HUD element-mask rule (element 14, torn down with 0/1/4/10 by sub_80081A4 at the RESULT countdown, asm00_1.s:10617-10621); popup 60614/1842->5094/1148/80, box 0 on all 80 frames; FLAG_HUD_LIVE bit 6 for the shared zero-enemy descriptor; Claude (Opus) agent, verified from a clean checkout)
cost $0.1844, 79 turns, 13 min, thinking high, role worker

expected: {'popup': ('5094', '1148', '80')}

```
verify_rows: wt/replay-F27b-20260916-122753-glm53fla89 (c8e2422) in /tmp/bnwt/verify-c8e2422
  popup          FAILED   5094/1148/80/5286        MATCH (isolated line)
verify_rows: PASS
```

session: /tmp/bn-pi/replay/20260916-122753-glm53fla89

balance 1.0 -> 1.0 but 3 other pi sessions were spending: credits not attributable
