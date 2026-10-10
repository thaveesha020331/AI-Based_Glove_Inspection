#include "sorting_types.h"

const char* decisionToString(const Decision decision) {
  switch (decision) {
    case Decision::ACCEPT:
      return "ACCEPT";
    case Decision::DEFECTIVE:
      return "DEFECTIVE";
    case Decision::WRONG_ORIENTATION:
      return "WRONG_ORIENTATION";
    default:
      return "NONE";
  }
}

const char* stateToString(const SortState state) {
  switch (state) {
    case SortState::WAIT_S1: return "WAIT_S1";
    case SortState::WAIT_S2: return "WAIT_S2";
    case SortState::WAIT_TRIGGER: return "WAIT_TRIGGER";
    case SortState::ACTUATING: return "ACTUATING";
    case SortState::VERIFYING: return "VERIFYING";
    case SortState::COMPLETE: return "COMPLETE";
    case SortState::ERROR_STATE: return "ERROR";
    default: return "IDLE";
  }
}

bool parseDecision(const String& value, Decision& decision) {
  if (value == "ACCEPT") {
    decision = Decision::ACCEPT;
  } else if (value == "DEFECTIVE") {
    decision = Decision::DEFECTIVE;
  } else if (value == "WRONG_ORIENTATION") {
    decision = Decision::WRONG_ORIENTATION;
  } else {
    return false;
  }
  return true;
}

