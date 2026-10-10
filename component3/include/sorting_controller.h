#pragma once

#include <Arduino.h>

#include "sorting_types.h"

class SortingController {
 public:
  void begin();
  bool queueEvent(const String& eventId, Decision decision, String& error);
  void update();
  const SortEvent& event() const { return event_; }
  bool busy() const;

 private:
  SortEvent event_;
  int previousS1_ = HIGH;
  int previousS2_ = HIGH;
  int previousV1_ = HIGH;
  int previousV2_ = HIGH;
  int activeRelayPin_ = -1;
  uint32_t stateStartedMs_ = 0;
  uint32_t triggerAtMs_ = 0;
  uint32_t relayOffAtMs_ = 0;
  uint32_t verifyStartedMs_ = 0;

  void processS1();
  void processS2();
  void processTrigger();
  void processRelayPulse();
  void processVerification();
  void activateRelay(uint8_t pin);
  void allRelaysOff();
  void fail(const String& status);
  static bool deadlineReached(uint32_t now, uint32_t deadline);
};

