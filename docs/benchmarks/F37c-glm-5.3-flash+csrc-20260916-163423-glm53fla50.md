# Replay F37c with hyper/glm-5.3-flash (high): FAIL

base 929c141 (2ecb7990b0b022d085b112c95a7d3709ba7a6e41 F37c object-Y pan + k0 bracket: cursor 130221/767/170->34902/232/170, windowclose 19168/1878/40->12538/1200/40 (verifier CONFIRMED pan/bracket/pose-refutation, rules clean; windowclose neg 50px fixture variance documented); 9 canaries 0; remainder = missing pickaxe object ~205/f, needs spawn/variant ticket (PARTIAL))
cost $0.8075, 253 turns, 45 min, thinking high, role worker, variant csrc

expected: {'cursor': ('34902', '232', '170'), 'windowclose': ('12538', '1200', '40')}

```
verify_rows: wt/replay-F37c-20260916-163423-glm53fla50 (8802a8d) in /tmp/bnwt/verify-8802a8d
  cursor         FAILED   25/19/170/186277         MISMATCH total,worst (claimed 34902/232/170/-)
  windowclose    FAILED   5047/1116/40/205743      MISMATCH total,worst (claimed 12538/1200/40/-)
verify_rows: FAIL
```

session: /tmp/bn-pi/replay/20260916-163423-glm53fla50

balance 173.8 -> 154.9 but 1 other pi sessions were spending: credits not attributable
