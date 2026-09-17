# Replay F37c with opencode/glm-5.3-flash (high): FAIL

base 929c141 (2ecb7990b0b022d085b112c95a7d3709ba7a6e41 F37c object-Y pan + k0 bracket: cursor 130221/767/170->34902/232/170, windowclose 19168/1878/40->12538/1200/40 (verifier CONFIRMED pan/bracket/pose-refutation, rules clean; windowclose neg 50px fixture variance documented); 9 canaries 0; remainder = missing pickaxe object ~205/f, needs spawn/variant ticket (PARTIAL))
cost $0.7603, 219 turns, 45 min, thinking high, role worker

expected: {'cursor': ('34902', '232', '170'), 'windowclose': ('12538', '1200', '40')}

```
verify_rows: wt/replay-F37c-20260916-131112-glm53fla70 (3e08f58) in /tmp/bnwt/verify-3e08f58
  cursor         FAILED   1/1/170/186279           MISMATCH total,worst (claimed 34902/232/170/-)
  windowclose    PASS     0/0/40/207166            MISMATCH total,worst (claimed 12538/1200/40/-)
verify_rows: FAIL
```

session: /tmp/bn-pi/replay/20260916-131112-glm53fla70

balance 1.0 -> 1.0 but 3 other pi sessions were spending: credits not attributable
