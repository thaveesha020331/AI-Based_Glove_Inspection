import importlib.util
from pathlib import Path

import pytest


DRIVER_PATH = Path(__file__).parents[3] / "Drivers" / "interface.py"


@pytest.fixture(scope="module")
def driver_module():
    spec = importlib.util.spec_from_file_location("component3_driver_test", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_semantic_relay_command_is_written_with_newline(driver_module):
    writes = []

    class FakeSerial:
        def write(self, payload):
            writes.append(payload)

        def flush(self):
            pass

    driver = driver_module.SerialTelemetryDriver(on_status=lambda _data: None)
    driver.send_command("camera_light_on")
    driver._write_pending_commands(FakeSerial())

    assert writes == [b"CAMERA_LIGHT_ON\n"]


def test_unknown_relay_command_is_rejected(driver_module):
    driver = driver_module.SerialTelemetryDriver(on_status=lambda _data: None)

    with pytest.raises(ValueError):
        driver.send_command("unsafe_arbitrary_command")
