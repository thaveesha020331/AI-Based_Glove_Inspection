# Hardware wiring and safety

Disconnect both the 12 V supply and USB before changing wiring. The ESP32-C3
GPIOs are 3.3 V only: never connect a 5 V sensor output directly to a GPIO.
Confirm the label and datasheet of each sensor and relay module before soldering.

## Pin assignment

| Function | GPIO | Notes |
|---|---:|---|
| S1 conveyor sensor | 0 | Level-shifted sensor output |
| S2 conveyor sensor | 1 | Level-shifted sensor output |
| V1 defective-bin sensor | 3 | Level-shifted sensor output |
| V2 wrong-orientation sensor | 10 | Level-shifted sensor output |
| Relay 1, defective nozzle | 5 | Active-low by default |
| Relay 2, orientation nozzle | 6 | Active-low by default |
| Relay 3, spare | 7 | Held off by firmware |
| Relay 4, spare | 4 | Held off by firmware |

GPIO2, GPIO8, and GPIO9 are intentionally unused because they may be connected
to boot-strapping or onboard functions on common SuperMini variants.

## Power distribution

```text
12 V DC supply
|-- relay contacts -> 12 V solenoid valves
`-- 12 V to 5 V buck converter
    |-- ESP32-C3 5 V input
    |-- relay module VCC
    |-- E18-D80NK sensors
    `-- level converter HV

ESP32 3V3 -> level converter LV
All low-voltage logic grounds -> common GND
```

Typical E18-D80NK wiring is brown = V+, blue = GND, and black = OUT, but the
actual device label takes precedence. Route each OUT signal through a suitable
5 V to 3.3 V interface before the corresponding GPIO.

## Solenoid circuit

For each normally-off valve, connect `12 V+ -> relay COM`, `relay NO ->
solenoid +`, and `solenoid - -> 12 V GND`. Use the normally-open contact so a
controller reset cannot continuously energize a valve. Add an appropriately
rated flyback diode or suppression device across a DC coil if the valve does
not contain one. Keep pneumatic and valve current wiring away from sensor leads.

## Bring-up order

1. Power the ESP32 alone and confirm all relay inputs are inactive at boot.
2. Connect and observe one level-shifted sensor at a time.
3. Test relay LEDs without the 12 V actuator circuit connected.
4. Connect one suppressed solenoid and verify a short pulse.
5. Add low-pressure air, guards, and an emergency isolation method.
6. Only then run timed sorting trials with gloves.

