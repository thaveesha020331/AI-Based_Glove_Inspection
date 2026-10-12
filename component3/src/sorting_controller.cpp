#include "sorting_controller.h"

#include "config.h"

void SortingController::begin() {
  pinMode(Config::PIN_S1, INPUT);
  pinMode(Config::PIN_S2, INPUT);
  pinMode(Config::PIN_V1, INPUT);
  pinMode(Config::PIN_V2, INPUT);
  pinMode(Config::PIN_RELAY_DEFECTIVE, OUTPUT);
  pinMode(Config::PIN_RELAY_ORIENTATION, OUTPUT);
  pinMode(Config::PIN_RELAY_SPARE_1, OUTPUT);
  pinMode(Config::PIN_RELAY_SPARE_2, OUTPUT);
  allRelaysOff();

  previousS1_ = digitalRead(Config::PIN_S1);
  previousS2_ = digitalRead(Config::PIN_S2);
  previousV1_ = digitalRead(Config::PIN_V1);
  previousV2_ = digitalRead(Config::PIN_V2);
}

bool SortingController::queueEvent(const String& eventId,
                                   const Decision decision,
                                   String& error) {
  if (busy()) {
    error = "sorter_busy";
    return false;
  }
  if (eventId.isEmpty() || eventId.length() > 64) {
    error = "invalid_event_id";
    return false;
  }

  event_ = SortEvent{};
  event_.eventId = eventId;
  event_.decision = decision;
  event_.state = SortState::WAIT_S1;
  event_.status = "WAITING_FOR_S1";
  stateStartedMs_ = millis();
  return true;
}

bool SortingController::busy() const {
  return event_.state != SortState::IDLE &&
         event_.state != SortState::COMPLETE &&
         event_.state != SortState::ERROR_STATE;
}

bool SortingController::deadlineReached(const uint32_t now,
                                        const uint32_t deadline) {
  return static_cast<int32_t>(now - deadline) >= 0;
}

void SortingController::update() {
  processS1();
  processS2();
  processTrigger();
  processRelayPulse();
  processVerification();
}

void SortingController::processS1() {
  const int current = digitalRead(Config::PIN_S1);
  if (event_.state == SortState::WAIT_S1 &&
      previousS1_ != Config::SENSOR_ACTIVE &&
      current == Config::SENSOR_ACTIVE) {
    event_.t1Us = micros();
    event_.state = SortState::WAIT_S2;
    event_.status = "S1_DETECTED";
    stateStartedMs_ = millis();
  }
  previousS1_ = current;
}

void SortingController::processS2() {
  const int current = digitalRead(Config::PIN_S2);
  if (event_.state == SortState::WAIT_S2 &&
      previousS2_ != Config::SENSOR_ACTIVE &&
      current == Config::SENSOR_ACTIVE) {
    event_.t2Us = micros();
    const uint32_t elapsedUs = event_.t2Us - event_.t1Us;
    if (elapsedUs == 0) {
      fail("TIMING_ERROR");
    } else {
      const float elapsedSeconds = elapsedUs / 1000000.0F;
      event_.speedMps = Config::SENSOR_DISTANCE_M / elapsedSeconds;
      if (event_.speedMps < Config::MIN_SPEED_MPS ||
          event_.speedMps > Config::MAX_SPEED_MPS) {
        fail("INVALID_SPEED");
      } else {
        event_.travelTimeMs =
            (Config::NOZZLE_DISTANCE_M / event_.speedMps) * 1000.0F;
        event_.triggerWaitMs = max(
            0.0F, event_.travelTimeMs - Config::ACTUATOR_DELAY_MS);
        triggerAtMs_ = millis() + static_cast<uint32_t>(event_.triggerWaitMs);
        event_.state = SortState::WAIT_TRIGGER;
        event_.status = "WAITING_FOR_TRIGGER";
      }
    }
  }

  if (event_.state == SortState::WAIT_S2 &&
      millis() - stateStartedMs_ > Config::S2_TIMEOUT_MS) {
    fail("S2_TIMEOUT");
  }
  previousS2_ = current;
}

void SortingController::processTrigger() {
  if (event_.state != SortState::WAIT_TRIGGER ||
      !deadlineReached(millis(), triggerAtMs_)) {
    return;
  }

  if (event_.decision == Decision::ACCEPT) {
    event_.status = "ACCEPT_NO_AIR_JET";
    event_.state = SortState::VERIFYING;
    verifyStartedMs_ = millis();
  } else if (event_.decision == Decision::DEFECTIVE) {
    activateRelay(Config::PIN_RELAY_DEFECTIVE);
  } else if (event_.decision == Decision::WRONG_ORIENTATION) {
    activateRelay(Config::PIN_RELAY_ORIENTATION);
  } else {
    fail("MISSING_DECISION");
  }
}

void SortingController::processRelayPulse() {
  if (event_.state != SortState::ACTUATING ||
      !deadlineReached(millis(), relayOffAtMs_)) {
    return;
  }

  allRelaysOff();
  verifyStartedMs_ = millis();
  event_.state = SortState::VERIFYING;
  event_.status = "WAITING_FOR_VERIFICATION";
}
void SortingController::processVerification() {
  const int v1 = digitalRead(Config::PIN_V1);
  const int v2 = digitalRead(Config::PIN_V2);
  if (event_.state != SortState::VERIFYING) {
    previousV1_ = v1;
    previousV2_ = v2;
    return;
  }

  const bool defectiveEdge = previousV1_ != Config::SENSOR_ACTIVE &&
                             v1 == Config::SENSOR_ACTIVE;
  const bool orientationEdge = previousV2_ != Config::SENSOR_ACTIVE &&
                               v2 == Config::SENSOR_ACTIVE;

  if (defectiveEdge && orientationEdge) {
    event_.actualDestination = "AMBIGUOUS";
    fail("MULTIPLE_DESTINATIONS");
  } else if (defectiveEdge) {
    event_.actualDestination = "DEFECTIVE_BIN";
    event_.status = event_.decision == Decision::DEFECTIVE
                        ? "CORRECT"
                        : "SORTING_ERROR";
    event_.state = SortState::COMPLETE;
  } else if (orientationEdge) {
    event_.actualDestination = "WRONG_ORIENTATION_BIN";
    event_.status = event_.decision == Decision::WRONG_ORIENTATION
                        ? "CORRECT"
                        : "SORTING_ERROR";
    event_.state = SortState::COMPLETE;
  } else if (millis() - verifyStartedMs_ > Config::VERIFY_TIMEOUT_MS) {
    if (event_.decision == Decision::ACCEPT) {
      // There is no accept-path sensor in the four-sensor prototype, so this
      // is explicitly reported as inferred rather than strongly verified.
      event_.actualDestination = "ACCEPT_PATH_UNVERIFIED";
      event_.status = "ACCEPT_INFERRED";
      event_.state = SortState::COMPLETE;
    } else {
      event_.actualDestination = "UNKNOWN";
      fail("VERIFICATION_TIMEOUT");
    }
  }

  previousV1_ = v1;
  previousV2_ = v2;
}
void SortingController::activateRelay(const uint8_t pin) {
  allRelaysOff();
  digitalWrite(pin, Config::RELAY_ON);
  activeRelayPin_ = pin;
  relayOffAtMs_ = millis() + Config::NOZZLE_PULSE_MS;
  event_.state = SortState::ACTUATING;
  event_.status = pin == Config::PIN_RELAY_DEFECTIVE
                      ? "DEFECTIVE_NOZZLE_ACTIVE"
                      : "ORIENTATION_NOZZLE_ACTIVE";
}

void SortingController::allRelaysOff() {
  digitalWrite(Config::PIN_RELAY_DEFECTIVE, Config::RELAY_OFF);
  digitalWrite(Config::PIN_RELAY_ORIENTATION, Config::RELAY_OFF);
  digitalWrite(Config::PIN_RELAY_SPARE_1, Config::RELAY_OFF);
  digitalWrite(Config::PIN_RELAY_SPARE_2, Config::RELAY_OFF);
  activeRelayPin_ = -1;
}

void SortingController::fail(const String& status) {
  allRelaysOff();
  event_.status = status;
  event_.state = SortState::ERROR_STATE;
}

