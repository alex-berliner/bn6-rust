# Replay F37c with hyper/glm-5.3-flash (high): FAIL

base 929c141 (2ecb7990b0b022d085b112c95a7d3709ba7a6e41 F37c object-Y pan + k0 bracket: cursor 130221/767/170->34902/232/170, windowclose 19168/1878/40->12538/1200/40 (verifier CONFIRMED pan/bracket/pose-refutation, rules clean; windowclose neg 50px fixture variance documented); 9 canaries 0; remainder = missing pickaxe object ~205/f, needs spawn/variant ticket (PARTIAL))
cost $0.3981, 176 turns, 18 min, thinking high, role worker, variant csrc2

expected: {'cursor': ('34902', '232', '170'), 'windowclose': ('12538', '1200', '40')}

```
verify_rows: wt/replay-F37c-20260916-233954-glm53fla60 (2dbe9f6) in /tmp/bnwt/verify-2dbe9f6
  cursor         FAILED   34857/211/170/221126     MISMATCH total,worst (claimed 34902/232/170/-)
  windowclose    FAILED   12642/1200/40/212823     MISMATCH total (claimed 12538/1200/40/-)
verify_rows: FAIL
```

session: /tmp/bn-pi/replay/20260916-233954-glm53fla60

balance 57.6 -> 48.5 but 1 other pi sessions were spending: credits not attributable
