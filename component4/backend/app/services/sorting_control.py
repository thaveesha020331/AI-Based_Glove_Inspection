"""Decision-to-relay control for the Component 3 sorting hardware."""

from datetime import datetime, timezone
from threading import RLock
import time


ORIENTATIONS = {"LeftHand", "RightHand"}


class SortingControlService:
    def __init__(
        self,
        command_sender,
        expected_orientation="LeftHand",
        warning_threshold=3,
        command_attempts=3,
        command_retry_delay=0.04,
    ):
        self._command_sender = command_sender
        self._lock = RLock()
        self.expected_orientation = self._normalize_orientation(expected_orientation)
        self.warning_threshold = max(int(warning_threshold), 1)
        self.command_attempts = max(int(command_attempts), 1)
        self.command_retry_delay = max(float(command_retry_delay), 0.0)
        self.automatic_enabled = True
        self.camera_light_requested = False
        self.warning_active = False
        self.consecutive_rejects = 0
        self.total_decisions = 0
        self.total_rejected = 0
        self.last_action = None
        self.last_error = None

    @staticmethod
    def _normalize_orientation(value):
        normalized = str(value).strip().casefold()
        mapping = {
            "left": "LeftHand",
            "lefthand": "LeftHand",
            "right": "RightHand",
            "righthand": "RightHand",
        }
        result = mapping.get(normalized)
        if result not in ORIENTATIONS:
            raise ValueError("expected_orientation must be LeftHand or RightHand.")
        return result

    def _send(self, command):
        last_error = "Serial command was not accepted."
        for attempt in range(self.command_attempts):
            try:
                if bool(self._command_sender(command)):
                    self.last_error = None
                    return True
                last_error = "Serial command was not accepted."
            except (RuntimeError, ValueError, OSError) as error:
                last_error = str(error)
            if attempt + 1 < self.command_attempts and self.command_retry_delay:
                time.sleep(self.command_retry_delay)
        self.last_error = last_error
        return False

    def snapshot(self):
        with self._lock:
            return {
                "automatic_enabled": self.automatic_enabled,
                "expected_orientation": self.expected_orientation,
                "camera_light_requested": self.camera_light_requested,
                "warning_active": self.warning_active,
                "warning_threshold": self.warning_threshold,
                "consecutive_rejects": self.consecutive_rejects,
                "total_decisions": self.total_decisions,
                "total_rejected": self.total_rejected,
                "last_action": dict(self.last_action) if self.last_action else None,
                "last_error": self.last_error,
                "relay_roles": {
                    "relay1": "damaged_glove_reject",
                    "relay2": "wrong_orientation_reject",
                    "relay3": "camera_light",
                    "relay4": "warning_light",
                },
            }

    def configure(self, expected_orientation=None, automatic_enabled=None):
        with self._lock:
            if expected_orientation is not None:
                self.expected_orientation = self._normalize_orientation(expected_orientation)
            if automatic_enabled is not None:
                if not isinstance(automatic_enabled, bool):
                    raise ValueError("automatic_enabled must be boolean.")
                self.automatic_enabled = automatic_enabled
            return self.snapshot()

    def set_camera_light(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("on must be boolean.")
        with self._lock:
            command = "CAMERA_LIGHT_ON" if enabled else "CAMERA_LIGHT_OFF"
            if self._send(command):
                self.camera_light_requested = enabled
            return self.snapshot()

    def reset_warning(self):
        with self._lock:
            if self._send("WARNING_OFF"):
                self.warning_active = False
                self.consecutive_rejects = 0
            return self.snapshot()

    def process_decision(self, orientation=None, defective=False, source="external"):
        if not isinstance(defective, bool):
            raise ValueError("defective must be boolean.")
        normalized_orientation = None
        if orientation is not None:
            normalized_orientation = self._normalize_orientation(orientation)
        if normalized_orientation is None and not defective:
            raise ValueError("A decision requires an orientation or defective=true.")

        with self._lock:
            timestamp = datetime.now(timezone.utc).isoformat()
            if not self.automatic_enabled:
                self.last_action = {
                    "result": "ignored",
                    "reason": "automatic_sorting_disabled",
                    "orientation": normalized_orientation,
                    "defective": defective,
                    "source": source,
                    "timestamp": timestamp,
                }
                return self.snapshot()

            self.total_decisions += 1
            reason = "accepted"
            command = None
            if defective:
                reason = "damaged_glove"
                command = "DEFECT_PULSE"
            elif normalized_orientation and normalized_orientation != self.expected_orientation:
                reason = "wrong_orientation"
                command = "ORIENTATION_PULSE"

            command_queued = True
            if command:
                command_queued = self._send(command)
                if command_queued:
                    self.consecutive_rejects += 1
                    self.total_rejected += 1
                    if self.consecutive_rejects >= self.warning_threshold and not self.warning_active:
                        if self._send("WARNING_ON"):
                            self.warning_active = True
            else:
                self.consecutive_rejects = 0

            self.last_action = {
                "result": "rejected" if command else "accepted",
                "reason": reason,
                "orientation": normalized_orientation,
                "defective": defective,
                "source": str(source),
                "command": command,
                "command_queued": command_queued,
                "timestamp": timestamp,
            }
            return self.snapshot()
