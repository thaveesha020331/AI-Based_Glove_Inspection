# Component 3 - Real-Time IoT Sorting and Verification

Component 3 is the physical execution layer of the glove inspection system. It
does not classify a glove again. Instead, it receives Component 2's final
decision, measures conveyor motion, operates the correct pneumatic nozzle at
the calculated time, and verifies the resulting destination.

## Responsibilities

- Receive `ACCEPT`, `DEFECTIVE`, or `WRONG_ORIENTATION` decisions over HTTP.
- Preserve the Component 2 `event_id` throughout the sorting cycle.
- Use S1 and S2 timestamps to estimate conveyor speed.
- Compensate for relay, solenoid, and pneumatic response delay.
- Keep relays normally off and generate a short, non-blocking air pulse.
- Verify the defective and wrong-orientation bins with V1 and V2.
- Expose live cycle status for integration with the PC and Component 4.

## Processing flow

```text
Component 2 decision -> POST /decision -> WAIT_S1 -> WAIT_S2
  -> calculate speed and trigger time -> actuate (when required)
  -> verify destination -> expose result through GET /status
```

`ACCEPT` continues along the normal conveyor path without an air jet.
`DEFECTIVE` uses nozzle 1, while `WRONG_ORIENTATION` uses nozzle 2.

## Repository layout

```text
component3/
|-- include/       Firmware configuration, data types, and controller API
|-- src/           ESP32-C3 firmware and sorting state machine
|-- calibration/   Measured geometry and timing parameters
|-- simulation/    Host-side timing model and automated tests
|-- tools/         PC-side HTTP utilities
|-- docs/          Wiring, API, and validation guidance
`-- logs/          Runtime/calibration log output (generated files ignored)
```

## Hardware summary

The prototype uses an ESP32-C3 SuperMini, four E18-D80NK-style sensors, a
relay module, two 12 V solenoid valves, and a 12 V to 5 V buck converter.
Sensor outputs must be translated to 3.3 V before reaching ESP32 GPIO pins.
All logic supplies must share a common ground.

## Quick start

1. Copy `include/secrets.example.h` to `include/secrets.h` and enter Wi-Fi
   credentials.
2. Check the distances and response timing in `include/config.h` against the
   measured values documented under `calibration/`.
3. Build and upload the firmware using PlatformIO.
4. POST a unique decision event to `/decision`.
5. Poll `/status` using `tools/send_decision.py` or the Component 4 service.

See the documents under `docs/` before connecting sensors, relays, or valves.
