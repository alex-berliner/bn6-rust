# Replay F21b with hyper/glm-5.3-flash (high): FAIL

base 91f2276 (9aa72e9a6ec683c01a208bb2d5a49d96952344b2 F21b result tail+slide: tilemap-column slide (j -30+2/f, hold 16), backdrop seed from RESULT_ARRIVAL; result 408337/31895/40->190633/24647/40 (offset 15->31), late-out 69986->2824, late-in 24689->5428; field iso 0->1048 / int +36k reported, all else identical)
cost $0.6030, 181 turns, 40 min, thinking high, role worker, variant csrc2

expected: {'result': ('190633', '24647', '40')}

```
verify_rows: wt/replay-F21b-20260916-225929-glm53fla96 (88725dc) in /tmp/bnwt/verify-88725dc
  result         FAILED   143117/22902/40/236897   MISMATCH total,worst (claimed 190633/24647/40/-)
verify_rows: FAIL
```

session: /tmp/bn-pi/replay/20260916-225929-glm53fla96

balance 72.5 -> 57.6 but 1 other pi sessions were spending: credits not attributable
