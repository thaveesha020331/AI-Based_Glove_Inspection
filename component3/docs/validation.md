# Validation plan

## Bench tests

Run these stages independently before an integrated conveyor trial:

1. Trigger S1 and S2 at a known interval and compare calculated speed with a
   reference measurement.
2. Confirm invalid speed and missing-S2 cases enter an error state without
   energizing a relay.
3. Measure the relay-to-air response and update the actuator delay calibration.
4. Confirm `DEFECTIVE` pulses only relay 1 and `WRONG_ORIENTATION` only relay 2.
5. Trigger V1 and V2 separately and confirm matching and mismatching outcomes.
6. Disconnect a verification sensor and confirm the timeout is reported.
7. Submit a second event during a cycle and confirm HTTP 409 is returned.

The host-side regression suite is run with:

```powershell
python -m unittest discover -s component3/simulation -v
```

## Research trial records

For each glove, record event ID, decision, S1/S2 timestamps, speed, trigger
delay, expected destination, actual destination, terminal status, and manual
ground truth. Report sorting accuracy per decision class, verification timeout
rate, timing error, and latency distribution. Keep failed trials in the data.

## Known limitation

The current four-sensor prototype has V1 at the defective bin and V2 at the
wrong-orientation bin. It can directly verify both diverted paths, but it can
only infer an accepted glove when neither diverted-bin sensor triggers. The
firmware labels this outcome `ACCEPT_INFERRED` and the destination
`ACCEPT_PATH_UNVERIFIED` so it is not misreported as strong verification.

A final research prototype should add an accept-path sensor (`V_ACCEPT`) or use
another sensing arrangement that identifies all three destinations directly.

