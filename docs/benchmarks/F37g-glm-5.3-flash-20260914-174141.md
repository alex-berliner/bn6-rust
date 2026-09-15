# Replay F37g with hyper/glm-5.3-flash (high): PASS

base 8e73c3c (4671a84cff40687ea73e80bfb9c4ad3737667854 F37g window mark during Closing: windowclose 1458/162/40->0/0/40, cursor 20->3/3/170 (verifier CONFIRMED paired control: result 58457 pre-exists byte-identical on main, mark mechanism + scope clean); result bottom strip needs own ticket (PARTIAL))
cost $0.1791, 79 turns, 17 min, thinking high, role worker

expected: {'windowclose': ('0', '0', '40')}

```
verify_rows: wt/replay-F37g-20260914-174141 (184eea4) in /tmp/bnwt/verify-184eea4
  windowclose    PASS     0/0/40/207166            MATCH
verify_rows: PASS
```

session: /tmp/bn-pi/replay/20260914-174141

balance 19.3 -> 15.1 but 1 other pi sessions were spending: credits not attributable
