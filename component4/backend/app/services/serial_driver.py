"""Lifecycle manager for the Component 3 serial driver."""

import atexit
import importlib.util
from pathlib import Path
from threading import Lock, Thread

from app.services.sorting_live import sorting_telemetry


class SerialDriverManager:
    def __init__(self, driver_path, port, baud_rate):
        self.driver_path = Path(driver_path)
        self.port = port
        self.baud_rate = int(baud_rate)
        self._lock = Lock()
        self._driver = None
        self._thread = None
        self._registered_exit = False

    def ensure_started(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            spec = importlib.util.spec_from_file_location(
                "component3_serial_interface", self.driver_path
            )
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Cannot load serial driver: {self.driver_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._driver = module.SerialTelemetryDriver(
                on_status=sorting_telemetry.update,
                port=self.port,
                baud_rate=self.baud_rate,
            )
            self._thread = Thread(
                target=self._driver.run,
                name="component3-serial-driver",
                daemon=True,
            )
            self._thread.start()
            if not self._registered_exit:
                atexit.register(self.stop)
                self._registered_exit = True

    def status(self):
        with self._lock:
            return {
                "running": bool(self._thread and self._thread.is_alive()),
                "state": getattr(self._driver, "state", "not_started"),
                "port": self.port,
                "baud_rate": self.baud_rate,
                "last_error": getattr(self._driver, "last_error", None),
            }

    def stop(self):
        with self._lock:
            driver = self._driver
            thread = self._thread
        if driver is not None:
            driver.stop()
        if thread is not None and thread.is_alive():
            thread.join(timeout=1)

