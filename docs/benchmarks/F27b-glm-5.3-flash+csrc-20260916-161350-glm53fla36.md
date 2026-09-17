# Replay F27b with hyper/glm-5.3-flash (high): PASS

base 9d07a63 (858acb2b470ab9ad4853790668de8cc23b9a79e3 F27b popup: emotion window on canon's HUD element-mask rule (element 14, torn down with 0/1/4/10 by sub_80081A4 at the RESULT countdown, asm00_1.s:10617-10621); popup 60614/1842->5094/1148/80, box 0 on all 80 frames; FLAG_HUD_LIVE bit 6 for the shared zero-enemy descriptor; Claude (Opus) agent, verified from a clean checkout)
cost $0.1867, 81 turns, 15 min, thinking high, role worker, variant csrc

expected: {'popup': ('5094', '1148', '80')}

```
verify_rows: wt/replay-F27b-20260916-161350-glm53fla36 (a9db8dd) in /tmp/bnwt/verify-a9db8dd
  popup          FAILED   5094/1148/80/5286        MATCH (isolated line)
verify_rows: PASS
```

session: /tmp/bn-pi/replay/20260916-161350-glm53fla36

balance 179.4 -> 175.1 but 1 other pi sessions were spending: credits not attributable
