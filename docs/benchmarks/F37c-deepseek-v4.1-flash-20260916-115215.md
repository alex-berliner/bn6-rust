# Replay F37c with opencode/deepseek-v4.1-flash (high): FAIL

base 929c141 (2ecb7990b0b022d085b112c95a7d3709ba7a6e41 F37c object-Y pan + k0 bracket: cursor 130221/767/170->34902/232/170, windowclose 19168/1878/40->12538/1200/40 (verifier CONFIRMED pan/bracket/pose-refutation, rules clean; windowclose neg 50px fixture variance documented); 9 canaries 0; remainder = missing pickaxe object ~205/f, needs spawn/variant ticket (PARTIAL))
cost $1.3571, 110 turns, 22 min, thinking high, role worker

expected: {'cursor': ('34902', '232', '170'), 'windowclose': ('12538', '1200', '40')}

```
verify_rows: wt/replay-F37c-20260916-115215 (ff13550) in /tmp/bnwt/verify-ff13550
  cursor         FAILED   34857/211/170/221126     MISMATCH total,worst (claimed 34902/232/170/-)
  windowclose    FAILED   12538/1200/40/212849     MATCH (isolated line)
verify_rows: FAIL
```

session: /tmp/bn-pi/replay/20260916-115215

balance 1.0 -> 1.0 but 7 other pi sessions were spending: credits not attributable
