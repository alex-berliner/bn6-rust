# Replay F37g with opencode/deepseek-v4.1-flash (high): PASS

base 8e73c3c (4671a84cff40687ea73e80bfb9c4ad3737667854 F37g window mark during Closing: windowclose 1458/162/40->0/0/40, cursor 20->3/3/170 (verifier CONFIRMED paired control: result 58457 pre-exists byte-identical on main, mark mechanism + scope clean); result bottom strip needs own ticket (PARTIAL))
cost $0.3201, 44 turns, 10 min, thinking high, role worker

expected: {'windowclose': ('0', '0', '40')}

```
verify_rows: wt/replay-F37g-20260916-121535 (c09d5c9) in /tmp/bnwt/verify-c09d5c9
  windowclose    PASS     0/0/40/207166            MATCH (isolated line)
verify_rows: PASS
```

session: /tmp/bn-pi/replay/20260916-121535

balance 1.0 -> 1.0 but 7 other pi sessions were spending: credits not attributable
