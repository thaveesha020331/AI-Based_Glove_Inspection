"""Dashboard-controlled real-time glove orientation inference."""

from collections import deque
from pathlib import Path
from threading import Condition, Event, RLock, Thread
import time


IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


class LiveOrientationWorker:
    def __init__(
        self,
        model_path,
        camera_index=0,
        classes=("LeftHand", "RightHand"),
        image_size=192,
        smoothing_window=7,
        minimum_confidence=0.80,
        clear_after_frames=4,
    ):
        self.model_path = Path(model_path)
        self.camera_index = int(camera_index)
        self.classes = tuple(classes)
        self.image_size = int(image_size)
        self.smoothing_window = max(int(smoothing_window), 3)
        self.minimum_confidence = float(minimum_confidence)
        self.clear_after_frames = max(int(clear_after_frames), 1)
        self._lock = RLock()
        self._condition = Condition(self._lock)
        self._stop_event = Event()
        self._thread = None
        self._capture = None
        self._frame_jpeg = None
        self._version = 0
        self._state = "stopped"
        self._error = None
        self._raw_prediction = None
        self._raw_confidence = None
        self._stable_prediction = None
        self._stable_confidence = None
        self._probabilities = {name: 0.0 for name in self.classes}
        self._fps = 0.0
        self._inference_ms = None
        self._frame_count = 0

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self.snapshot()
            self._stop_event.clear()
            self._state = "starting"
            self._error = None
            self._raw_prediction = None
            self._raw_confidence = None
            self._stable_prediction = None
            self._stable_confidence = None
            self._probabilities = {name: 0.0 for name in self.classes}
            self._fps = 0.0
            self._inference_ms = None
            self._frame_count = 0
            self._frame_jpeg = None
            self._thread = Thread(
                target=self._run,
                name="live-orientation-inference",
                daemon=True,
            )
            self._thread.start()
            self._publish_locked()
        return self.snapshot()

    def stop(self):
        self._stop_event.set()
        with self._lock:
            capture = self._capture
        if capture is not None:
            capture.release()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        with self._lock:
            self._state = "stopped"
            self._capture = None
            self._publish_locked()
        return self.snapshot()

    def snapshot(self):
        with self._lock:
            return {
                "state": self._state,
                "running": self._state in {"starting", "running"},
                "error": self._error,
                "camera_index": self.camera_index,
                "model": self.model_path.name,
                "classes": list(self.classes),
                "raw_prediction": self._raw_prediction,
                "raw_confidence": self._raw_confidence,
                "stable_prediction": self._stable_prediction,
                "stable_confidence": self._stable_confidence,
                "probabilities": dict(self._probabilities),
                "fps": round(self._fps, 2),
                "inference_ms": self._inference_ms,
                "frame_count": self._frame_count,
                "stability_window": self.smoothing_window,
                "minimum_confidence": self.minimum_confidence,
                "decision_state": self._decision_state_locked(),
            }

    def _decision_state_locked(self):
        if self._state != "running":
            return self._state
        if self._stable_prediction is not None:
            return "detected"
        if self._frame_count < self.smoothing_window:
            return "analyzing"
        return "uncertain"

    def wait_for_update(self, version, timeout=1.0):
        with self._condition:
            self._condition.wait_for(lambda: self._version != version, timeout=timeout)
            current_version = self._version
        return self.snapshot(), current_version

    def wait_for_frame(self, previous_frame, timeout=1.0):
        with self._condition:
            self._condition.wait_for(
                lambda: self._frame_jpeg is not None and self._frame_jpeg is not previous_frame,
                timeout=timeout,
            )
            return self._frame_jpeg

    def _publish_locked(self):
        self._version += 1
        self._condition.notify_all()

    def _set_error(self, message):
        with self._lock:
            self._state = "error"
            self._error = str(message)
            self._publish_locked()

    def _run(self):
        try:
            import cv2
            import numpy as np
            import torch

            if not self.model_path.is_file():
                raise FileNotFoundError(f"Model not found: {self.model_path}")
            torch.set_num_threads(max(1, min(torch.get_num_threads(), 4)))
            model = torch.jit.load(str(self.model_path), map_location="cpu").eval()
            capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not capture.isOpened():
                capture.release()
                capture = cv2.VideoCapture(self.camera_index)
            if not capture.isOpened():
                raise RuntimeError(f"Cannot open webcam index {self.camera_index}")
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            capture.set(cv2.CAP_PROP_FPS, 30)
            with self._lock:
                self._capture = capture
                self._state = "running"
                self._error = None
                self._publish_locked()

            history = deque(maxlen=self.smoothing_window)
            ema = None
            stable_index = None
            uncertain_streak = 0
            previous_time = time.perf_counter()
            while not self._stop_event.is_set():
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Webcam stopped returning frames")
                started = time.perf_counter()
                tensor = self._preprocess(frame, cv2, np, torch)
                with torch.inference_mode():
                    logits = model(tensor)
                    if isinstance(logits, (tuple, list)):
                        logits = logits[0]
                    probabilities = torch.softmax(logits, dim=1)[0].cpu().numpy()
                inference_ms = (time.perf_counter() - started) * 1000

                ema = probabilities if ema is None else 0.28 * probabilities + 0.72 * ema
                raw_index = int(probabilities.argmax())
                candidate = int(ema.argmax())
                history.append(candidate)
                agreement = sum(index == candidate for index in history)
                required = max(3, int(len(history) * 0.7 + 0.5))
                is_confident = float(ema[candidate]) >= self.minimum_confidence
                if len(history) >= 3 and agreement >= required and is_confident:
                    stable_index = candidate
                    uncertain_streak = 0
                else:
                    uncertain_streak += 1
                    if uncertain_streak >= self.clear_after_frames:
                        stable_index = None

                now = time.perf_counter()
                instant_fps = 1.0 / max(now - previous_time, 1e-6)
                previous_time = now
                self._fps = instant_fps if self._fps == 0 else self._fps * 0.85 + instant_fps * 0.15
                raw_name = self.classes[raw_index]
                stable_name = self.classes[stable_index] if stable_index is not None else None
                annotated = self._annotate(
                    frame,
                    cv2,
                    stable_name,
                    float(ema.max()),
                    inference_ms,
                    uncertain=stable_index is None and uncertain_streak >= self.clear_after_frames,
                )
                encoded, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if not encoded:
                    continue
                with self._lock:
                    self._raw_prediction = raw_name
                    self._raw_confidence = round(float(probabilities[raw_index]), 4)
                    self._stable_prediction = stable_name
                    self._stable_confidence = round(float(ema[stable_index]), 4) if stable_index is not None else None
                    self._probabilities = {
                        name: round(float(ema[index]), 4)
                        for index, name in enumerate(self.classes)
                    }
                    self._inference_ms = round(inference_ms, 2)
                    self._frame_count += 1
                    self._frame_jpeg = jpeg.tobytes()
                    self._publish_locked()
        except ImportError as error:
            if not self._stop_event.is_set():
                detail = str(error)
                if "_C" in detail or "DLL load failed" in detail:
                    detail += (
                        ". The backend is using a Python installation with a broken "
                        "Torch package. Stop it and run component4/backend/start_backend.ps1 "
                        "to use the repository .venv."
                    )
                self._set_error(detail)
        except Exception as error:
            if not self._stop_event.is_set():
                self._set_error(error)
        finally:
            with self._lock:
                capture = self._capture
                self._capture = None
            if capture is not None:
                capture.release()
            if self._stop_event.is_set():
                with self._lock:
                    self._state = "stopped"
                    self._publish_locked()

    def _preprocess(self, frame, cv2, np, torch):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        short_side = min(height, width)
        crop_size = max(1, int(short_side / 1.14))
        y1 = max(0, (height - crop_size) // 2)
        x1 = max(0, (width - crop_size) // 2)
        crop = rgb[y1:y1 + crop_size, x1:x1 + crop_size]
        image = cv2.resize(crop, (self.image_size, self.image_size), interpolation=cv2.INTER_LINEAR)
        image = image.astype(np.float32) / 255.0
        image = (image - np.asarray(IMAGENET_MEAN, dtype=np.float32)) / np.asarray(IMAGENET_STD, dtype=np.float32)
        return torch.from_numpy(image.transpose(2, 0, 1)).unsqueeze(0)

    @staticmethod
    def _annotate(frame, cv2, prediction, confidence, inference_ms, uncertain=False):
        output = frame.copy()
        label = "No glove / uncertain" if uncertain else "Analyzing..." if prediction is None else f"{prediction}  {confidence * 100:.1f}%"
        colour = (37, 180, 117) if prediction is not None else (30, 150, 230)
        cv2.rectangle(output, (14, 14), (390, 78), (16, 28, 45), -1)
        cv2.putText(output, label, (28, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.75, colour, 2, cv2.LINE_AA)
        cv2.putText(output, f"Inference {inference_ms:.1f} ms", (28, 67), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (210, 220, 230), 1, cv2.LINE_AA)
        return output

