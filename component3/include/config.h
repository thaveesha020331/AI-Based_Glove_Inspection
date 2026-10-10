#pragma once

#include <Arduino.h>

namespace Config {

// ESP32-C3 SuperMini pin plan. Avoid GPIO2, GPIO8, and GPIO9 because common
// boards use them for boot-strapping or onboard functions.
constexpr uint8_t PIN_S1 = 0;
constexpr uint8_t PIN_S2 = 1;
constexpr uint8_t PIN_V1 = 3;
constexpr uint8_t PIN_V2 = 10;
constexpr uint8_t PIN_RELAY_DEFECTIVE = 5;
constexpr uint8_t PIN_RELAY_ORIENTATION = 6;
constexpr uint8_t PIN_RELAY_SPARE_1 = 7;
constexpr uint8_t PIN_RELAY_SPARE_2 = 4;

constexpr uint8_t SENSOR_ACTIVE = LOW;
constexpr uint8_t RELAY_ON = LOW;
constexpr uint8_t RELAY_OFF = HIGH;

constexpr float SENSOR_DISTANCE_M = 0.20F;
constexpr float NOZZLE_DISTANCE_M = 0.30F;
constexpr uint32_t ACTUATOR_DELAY_MS = 80;
constexpr uint32_t NOZZLE_PULSE_MS = 120;
constexpr uint32_t S2_TIMEOUT_MS = 3000;
constexpr uint32_t VERIFY_TIMEOUT_MS = 2000;
constexpr float MIN_SPEED_MPS = 0.01F;
constexpr float MAX_SPEED_MPS = 5.0F;

}  // namespace Config

