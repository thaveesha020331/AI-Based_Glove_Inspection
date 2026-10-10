#pragma once

#include <Arduino.h>

enum class Decision : uint8_t {
  NONE,
  ACCEPT,
  DEFECTIVE,
  WRONG_ORIENTATION,
};

enum class SortState : uint8_t {
  IDLE,
  WAIT_S1,
  WAIT_S2,
  WAIT_TRIGGER,
  ACTUATING,
  VERIFYING,
  COMPLETE,
  ERROR_STATE,
};

struct SortEvent {
  String eventId;
  Decision decision = Decision::NONE;
  SortState state = SortState::IDLE;
  uint32_t t1Us = 0;
  uint32_t t2Us = 0;
  float speedMps = 0.0F;
  float travelTimeMs = 0.0F;
  float triggerWaitMs = 0.0F;
  String actualDestination = "UNKNOWN";
  String status = "IDLE";
};

const char* decisionToString(Decision decision);
const char* stateToString(SortState state);
bool parseDecision(const String& value, Decision& decision);

