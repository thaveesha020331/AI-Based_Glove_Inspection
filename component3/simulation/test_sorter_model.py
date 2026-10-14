import unittest

from sorter_model import (
    Decision,
    TimingConfig,
    calculate_timing,
    expected_destination,
    verify_destination,
)


class TimingModelTests(unittest.TestCase):
    def test_calculates_speed_and_compensated_delay(self) -> None:
        result = calculate_timing(1_000_000, 1_400_000)

        self.assertAlmostEqual(result.speed_mps, 0.5)
        self.assertAlmostEqual(result.travel_time_ms, 600.0)
        self.assertAlmostEqual(result.trigger_wait_ms, 520.0)

    def test_clamps_trigger_wait_when_actuator_is_slower_than_travel(self) -> None:
        config = TimingConfig(actuator_delay_ms=1000.0)

        result = calculate_timing(10_000, 410_000, config)

        self.assertEqual(result.trigger_wait_ms, 0.0)

    def test_rejects_non_monotonic_timestamps(self) -> None:
        with self.assertRaisesRegex(ValueError, "later than"):
            calculate_timing(500, 500)

    def test_rejects_speed_outside_calibrated_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside calibrated range"):
            calculate_timing(0, 10_000_000_000)

    def test_rejects_invalid_calibration(self) -> None:
        with self.assertRaisesRegex(ValueError, "distances"):
            TimingConfig(sensor_distance_m=0)


class DestinationVerificationTests(unittest.TestCase):
    def test_maps_each_decision_to_expected_destination(self) -> None:
        self.assertEqual(expected_destination(Decision.DEFECTIVE), "DEFECTIVE_BIN")
        self.assertEqual(
            expected_destination(Decision.WRONG_ORIENTATION),
            "WRONG_ORIENTATION_BIN",
        )

    def test_reports_matching_diverted_bin_as_correct(self) -> None:
        self.assertEqual(
            verify_destination(Decision.DEFECTIVE, "DEFECTIVE_BIN"), "CORRECT"
        )

    def test_reports_wrong_bin_as_sorting_error(self) -> None:
        self.assertEqual(
            verify_destination(Decision.DEFECTIVE, "WRONG_ORIENTATION_BIN"),
            "SORTING_ERROR",
        )

    def test_labels_accept_result_as_inferred(self) -> None:
        self.assertEqual(
            verify_destination(Decision.ACCEPT, "ACCEPT_PATH_UNVERIFIED"),
            "ACCEPT_INFERRED",
        )


if __name__ == "__main__":
    unittest.main()

