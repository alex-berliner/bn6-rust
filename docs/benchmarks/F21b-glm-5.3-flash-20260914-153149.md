# Replay F21b with hyper/glm-5.3-flash (high): FAIL

base 91f2276 (9aa72e9a6ec683c01a208bb2d5a49d96952344b2 F21b result tail+slide: tilemap-column slide (j -30+2/f, hold 16), backdrop seed from RESULT_ARRIVAL; result 408337/31895/40->190633/24647/40 (offset 15->31), late-out 69986->2824, late-in 24689->5428; field iso 0->1048 / int +36k reported, all else identical)
cost $0.5167, 130 turns, 35 min, thinking high, role worker

expected: {'result': ('190633', '24647', '40')}

```
verify_rows: wt/replay-F21b-20260914-153149 (02d9cd1) in /tmp/bnwt/verify-02d9cd1
  result         FAILED   154776/23570/40/216551   MISMATCH total,worst (claimed 190633/24647/40/-)
verify_rows: FAIL
```

session: /tmp/bn-pi/replay/20260914-153149

balance 82.3 -> 55.0 but 2 other pi sessions were spending: credits not attributable
