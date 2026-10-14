"""Host-side timing model for the Component 3 sorter.

This module mirrors the firmware equations without requiring ESP32 hardware.
It is intended for calibration checks and regression tests, not control of a
physical actuator.
"""

from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    DEFECTIVE = "DEFECTIVE"
    WRONG_ORIENTATION = "WRONG_ORIENTATION"


@dataclass(frozen=True)
class TimingConfig:
    sensor_distance_m: float = 0.20
    nozzle_distance_m: float = 0.30
    actuator_delay_ms: float = 80.0
    minimum_speed_mps: float = 0.01
    maximum_speed_mps: float = 5.0

    def __post_init__(self) -> None:
        if self.sensor_distance_m <= 0 or self.nozzle_distance_m <= 0:
            raise ValueError("distances must be positive")
        if self.actuator_delay_ms < 0:
            raise ValueError("actuator delay cannot be negative")
        if not 0 < self.minimum_speed_mps < self.maximum_speed_mps:
            raise ValueError("invalid speed range")


@dataclass(frozen=True)
class TimingResult:
    speed_mps: float
    travel_time_ms: float
    trigger_wait_ms: float


def calculate_timing(
    t1_us: int, t2_us: int, config: TimingConfig = TimingConfig()
) -> TimingResult:
    """Calculate speed and compensated trigger delay from two timestamps."""
    elapsed_us = t2_us - t1_us
    if elapsed_us <= 0:
        raise ValueError("S2 timestamp must be later than S1 timestamp")

    speed = config.sensor_distance_m / (elapsed_us / 1_000_000)
    if not config.minimum_speed_mps <= speed <= config.maximum_speed_mps:
        raise ValueError(f"speed outside calibrated range: {speed:.4f} m/s")

    travel_time_ms = config.nozzle_distance_m / speed * 1_000
    trigger_wait_ms = max(0.0, travel_time_ms - config.actuator_delay_ms)
    return TimingResult(speed, travel_time_ms, trigger_wait_ms)


def expected_destination(decision: Decision) -> str:
    return {
        Decision.ACCEPT: "ACCEPT_PATH_UNVERIFIED",
        Decision.DEFECTIVE: "DEFECTIVE_BIN",
        Decision.WRONG_ORIENTATION: "WRONG_ORIENTATION_BIN",
    }[decision]


def verify_destination(decision: Decision, actual_destination: str) -> str:
    """Return the same terminal status vocabulary used by the firmware."""
    if decision is Decision.ACCEPT and actual_destination == "ACCEPT_PATH_UNVERIFIED":
        return "ACCEPT_INFERRED"
    return "CORRECT" if actual_destination == expected_destination(decision) else "SORTING_ERROR"

