# Calibration procedure

The values in `defaults.json` mirror the compile-time firmware defaults. They
are starting points, not experimental measurements.

## Geometry

1. Measure from the S1 detection line to the S2 detection line and record at
   least three readings.
2. Measure from the S2 detection line to the point at which the air jet must
   hit the glove.
3. Use the mean distances in both `defaults.json` and `include/config.h`.

## Actuator response

Record the interval from the relay command to usable air flow at the nozzle.
Repeat at least 20 times under the intended pressure, report mean and standard
deviation, and use a conservative measured delay. The trigger equation is:

```text
speed = sensor_distance / (t2 - t1)
travel_time = s2_to_nozzle_distance / speed
trigger_wait = max(0, travel_time - actuator_delay)
```

## Pulse and verification window

Start with a short pulse and increase it only until sorting is reliable. Long
pulses waste air and can disturb adjacent gloves. Set the verification timeout
long enough for the slowest valid glove to reach a bin sensor.

For traceability, save each calibration run as a CSV under `logs/` with the
date, supply pressure, conveyor setting, measured values, and operator notes.

