# Replay F34b with opencode/deepseek-v4.1-flash (high): PASS

base 1ca132f (92a01a9247e18d47ef89926a002af37745ca3cdf F34b result to 0: no intro fade on start_state==1 + megaman_col 2 + enemies 0; 93183->0; canaries 0, cursor +18 layout-churn; verifier CONFIRMED fade+peeks, churn verdict)
cost $0.5159, 68 turns, 16 min, thinking high, role worker

expected: {'result': ('0', '0', '40')}

```
verify_rows: wt/replay-F34b-20260916-113505 (3c7e576) in /tmp/bnwt/verify-3c7e576
  result         PASS     0/0/40/111839            MATCH (isolated line)
verify_rows: PASS
```

session: /tmp/bn-pi/replay/20260916-113505

balance 1.0 -> 1.0 but 7 other pi sessions were spending: credits not attributable
