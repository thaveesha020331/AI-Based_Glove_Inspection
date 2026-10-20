import pytest

from app.services.sorting_control import SortingControlService


@pytest.fixture()
def control():
    commands = []
    def send(command):
        commands.append(command)
        return True
    service = SortingControlService(send, expected_orientation="LeftHand", warning_threshold=3)
    service.commands = commands
    return service


def test_wrong_orientation_pulses_relay_two(control):
    result = control.process_decision(orientation="RightHand", defective=False)

    assert control.commands == ["ORIENTATION_PULSE"]
    assert result["last_action"]["reason"] == "wrong_orientation"
    assert result["consecutive_rejects"] == 1


def test_defect_has_priority_over_orientation(control):
    result = control.process_decision(orientation="RightHand", defective=True)

    assert control.commands == ["DEFECT_PULSE"]
    assert result["last_action"]["reason"] == "damaged_glove"


def test_warning_latches_after_consecutive_rejects(control):
    control.process_decision(orientation="RightHand")
    control.process_decision(orientation="RightHand")
    result = control.process_decision(orientation="RightHand")

    assert control.commands == [
        "ORIENTATION_PULSE", "ORIENTATION_PULSE", "ORIENTATION_PULSE", "WARNING_ON"
    ]
    assert result["warning_active"] is True

    accepted = control.process_decision(orientation="LeftHand")
    assert accepted["consecutive_rejects"] == 0
    assert accepted["warning_active"] is True

    reset = control.reset_warning()
    assert control.commands[-1] == "WARNING_OFF"
    assert reset["warning_active"] is False


def test_camera_light_uses_relay_three_semantic_command(control):
    on = control.set_camera_light(True)
    off = control.set_camera_light(False)

    assert control.commands == ["CAMERA_LIGHT_ON", "CAMERA_LIGHT_OFF"]
    assert on["camera_light_requested"] is True
    assert off["camera_light_requested"] is False


def test_empty_decision_is_rejected(control):
    with pytest.raises(ValueError):
        control.process_decision()
