"""Thread-safe in-memory telemetry store for the Component 3 serial bridge."""

from copy import deepcopy
from datetime import datetime, timezone
from math import isfinite
from threading import Condition, RLock


SENSOR_FIELDS = ("speed_s1", "speed_s2", "verify_v1", "verify_v2")
RELAY_FIELDS = ("relay1", "relay2", "relay3", "relay4")


def _boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "on", "active", "detected"}:
            return True
        if normalized in {"false", "0", "off", "inactive", "clear"}:
            return False
    raise ValueError("Sensor and relay values must be boolean.")


class SortingTelemetryStore:
    def __init__(self):
        self._lock = RLock()
        self._condition = Condition(self._lock)
        self._latest = None
        self._received_at = None
        self._version = 0
        self._speed_state = "idle"
        self._speed_distance_cm = 100.0
        self._speed_started_uptime_ms = None
        self._speed_elapsed_ms = None
        self._speed_mps = None
        self._speed_started_at = None
        self._speed_completed_at = None
        self._speed_error = None

    def _speed_snapshot_locked(self):
        return {
            "state": self._speed_state,
            "distance_cm": self._speed_distance_cm,
            "elapsed_ms": self._speed_elapsed_ms,
            "speed_mps": self._speed_mps,
            "speed_cmps": (
                round(self._speed_mps * 100, 3)
                if self._speed_mps is not None
                else None
            ),
            "started_at": self._speed_started_at,
            "completed_at": self._speed_completed_at,
            "error": self._speed_error,
        }

    def arm_speed_sync(self, distance_cm):
        try:
            distance_cm = float(distance_cm)
        except (TypeError, ValueError) as exc:
            raise ValueError("distance_cm must be a number.") from exc
        if not isfinite(distance_cm) or distance_cm <= 0 or distance_cm > 10000:
            raise ValueError("distance_cm must be between 0 and 10000.")

        with self._lock:
            self._speed_state = "waiting_s1"
            self._speed_distance_cm = round(distance_cm, 3)
            self._speed_started_uptime_ms = None
            self._speed_elapsed_ms = None
            self._speed_mps = None
            self._speed_started_at = None
            self._speed_completed_at = None
            self._speed_error = None
            self._version += 1
            self._condition.notify_all()
            return self._speed_snapshot_locked()

    def _update_speed_sync_locked(self, previous, current, received_at):
        previous_sensors = previous["sensors"] if previous else {}
        sensors = current["sensors"]
        s1_rising = sensors["speed_s1"] and not previous_sensors.get("speed_s1", False)
        s2_rising = sensors["speed_s2"] and not previous_sensors.get("speed_s2", False)

        if self._speed_state == "waiting_s1" and s1_rising:
            self._speed_started_uptime_ms = current["uptime_ms"]
            self._speed_started_at = received_at.isoformat()
            self._speed_state = "waiting_s2"
        elif self._speed_state == "waiting_s2" and s2_rising:
            elapsed_ms = current["uptime_ms"] - self._speed_started_uptime_ms
            if elapsed_ms <= 0:
                self._speed_state = "error"
                self._speed_error = "Controller uptime reset or S2 was detected too early."
                return
            self._speed_elapsed_ms = elapsed_ms
            distance_m = self._speed_distance_cm / 100.0
            self._speed_mps = round(distance_m / (elapsed_ms / 1000.0), 4)
            self._speed_completed_at = received_at.isoformat()
            self._speed_state = "complete"

    def update(self, payload):
        if not isinstance(payload, dict) or payload.get("type") != "c3_status":
            raise ValueError("type must be c3_status.")
        sensors = payload.get("sensors")
        relays = payload.get("relays")
        if not isinstance(sensors, dict) or not isinstance(relays, dict):
            raise ValueError("sensors and relays must be JSON objects.")

        try:
            uptime_ms = int(payload.get("uptime_ms", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("uptime_ms must be an integer.") from exc
        if uptime_ms < 0:
            raise ValueError("uptime_ms cannot be negative.")

        normalized = {
            "type": "c3_status",
            "uptime_ms": uptime_ms,
            "sensors": {field: _boolean(sensors.get(field, False)) for field in SENSOR_FIELDS},
            "relays": {field: _boolean(relays.get(field, False)) for field in RELAY_FIELDS},
        }
        received_at = datetime.now(timezone.utc)
        with self._lock:
            previous = self._latest
            self._update_speed_sync_locked(previous, normalized, received_at)
            self._latest = normalized
            self._received_at = received_at
            self._version += 1
            self._condition.notify_all()
        return self.snapshot()

    def wait_for_update(self, version, stale_seconds=3.0, timeout=1.0):
        with self._condition:
            self._condition.wait_for(
                lambda: self._version != version,
                timeout=timeout,
            )
            current_version = self._version
        return self.snapshot(stale_seconds), current_version

    def snapshot(self, stale_seconds=3.0):
        now = datetime.now(timezone.utc)
        with self._lock:
            latest = deepcopy(self._latest)
            received_at = self._received_at
        if latest is None or received_at is None:
            snapshot = {
                "type": "c3_status",
                "status": "waiting_for_driver",
                "online": False,
                "received_at": None,
                "age_ms": None,
                "uptime_ms": 0,
                "sensors": {field: False for field in SENSOR_FIELDS},
                "relays": {field: False for field in RELAY_FIELDS},
            }
            with self._lock:
                snapshot["speed_sync"] = self._speed_snapshot_locked()
            return snapshot
        age_ms = max(0, round((now - received_at).total_seconds() * 1000))
        online = age_ms <= max(float(stale_seconds), 0.1) * 1000
        result = {
            **latest,
            "status": "connected" if online else "stale",
            "online": online,
            "received_at": received_at.isoformat(),
            "age_ms": age_ms,
        }
        with self._lock:
            result["speed_sync"] = self._speed_snapshot_locked()
        return result

    def reset(self):
        with self._lock:
            self._latest = None
            self._received_at = None
            self._speed_state = "idle"
            self._speed_distance_cm = 100.0
            self._speed_started_uptime_ms = None
            self._speed_elapsed_ms = None
            self._speed_mps = None
            self._speed_started_at = None
            self._speed_completed_at = None
            self._speed_error = None
            self._version += 1
            self._condition.notify_all()


sorting_telemetry = SortingTelemetryStore()

