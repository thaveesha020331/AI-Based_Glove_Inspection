"""Low-latency ESP32 serial reader for Component 3 telemetry."""

import json
import os
import time
from threading import Event
from queue import Empty, Queue
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import serial


SERIAL_PORT = os.getenv("COMPONENT3_SERIAL_PORT", "COM7")
BAUD_RATE = int(os.getenv("COMPONENT3_BAUD_RATE", "115200"))
BACKEND_URL = os.getenv(
    "COMPONENT3_BACKEND_URL",
    "http://127.0.0.1:5000/api/v1/sorting/live",
)
SERIAL_TIMEOUT_SECONDS = float(os.getenv("COMPONENT3_SERIAL_TIMEOUT", "0.05"))
RECONNECT_DELAY_SECONDS = float(os.getenv("COMPONENT3_RECONNECT_DELAY", "0.25"))

VALID_COMMANDS = {
    "DEFECT_PULSE", "ORIENTATION_PULSE",
    "CAMERA_LIGHT_ON", "CAMERA_LIGHT_OFF",
    "WARNING_ON", "WARNING_OFF", "ALL_OFF",
    "R1_ON", "R1_OFF", "R2_ON", "R2_OFF",
    "R3_ON", "R3_OFF", "R4_ON", "R4_OFF",
}


def publish_status(data):
    """Fallback publisher used when this file is run as a standalone process."""
    request = Request(
        BACKEND_URL,
        data=json.dumps(data, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Connection": "keep-alive"},
    )
    try:
        with urlopen(request, timeout=0.35) as response:
            return response.status == 202
    except (HTTPError, URLError, TimeoutError):
        return False


def read_status(line):
    """Return Component 3 status JSON and ignore diagnostics or other messages."""
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("type") != "c3_status":
        return None
    return data


class SerialTelemetryDriver:
    """Continuously read the ESP32 and deliver status without terminal output."""

    def __init__(self, on_status=None, port=SERIAL_PORT, baud_rate=BAUD_RATE):
        self.on_status = on_status or publish_status
        self.port = port
        self.baud_rate = int(baud_rate)
        self.stop_event = Event()
        self.command_queue = Queue()
        self.state = "stopped"
        self.last_error = None

    def send_command(self, command):
        normalized = str(command).strip().upper()
        if normalized not in VALID_COMMANDS:
            raise ValueError(f"Unsupported ESP32 command: {normalized}")
        self.command_queue.put_nowait(normalized)
        return True

    def _write_pending_commands(self, serial_connection):
        while True:
            try:
                command = self.command_queue.get_nowait()
            except Empty:
                return
            serial_connection.write(f"{command}\n".encode("ascii"))
            serial_connection.flush()

    def stop(self):
        self.stop_event.set()

    def run(self):
        while not self.stop_event.is_set():
            self.state = "connecting"
            try:
                with serial.Serial(
                    port=self.port,
                    baudrate=self.baud_rate,
                    timeout=SERIAL_TIMEOUT_SECONDS,
                ) as serial_connection:
                    self.state = "connected"
                    self.last_error = None
                    while not self.stop_event.is_set():
                        self._write_pending_commands(serial_connection)
                        raw_line = serial_connection.readline()
                        if not raw_line:
                            continue
                        status = read_status(
                            raw_line.decode("utf-8", errors="ignore").strip()
                        )
                        if status is not None:
                            self.on_status(status)
            except (serial.SerialException, OSError) as error:
                self.state = "error"
                self.last_error = str(error)
                self.stop_event.wait(RECONNECT_DELAY_SECONDS)
        self.state = "stopped"


def run():
    SerialTelemetryDriver().run()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass

