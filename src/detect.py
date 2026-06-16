"""
detect.py
---------
Real-time webcam loop with:
  • MTCNN face detection (fallback: Haar cascade)
  • Emotion inference using PyTorch emotion_model.pth
  • 2-second rolling-window majority vote (smoothing)
  • Callback hook → triggers music engine on emotion change
"""

import sys
import time
import collections
from pathlib import Path
from typing import Optional, Callable

import cv2
import numpy as np
import torch

# Allow sibling imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from preprocess import preprocess_face, NUM_CLASSES, EMOTION_LABELS
from train import EmotionCNN

# ── Constants ──────────────────────────────────────────────────────────────────
PROJECT_ROOT  = Path(__file__).resolve().parent.parent
MODEL_PATH    = PROJECT_ROOT / "models" / "emotion_model.pth"
HAAR_XML      = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

# Inference FPS cap — run model every N frames
INFER_EVERY_N_FRAMES = 3
MAX_WINDOW_FRAMES    = 20          # ~2 s rolling window

# Display colours (BGR)
COLOR_BOX  = (0, 220, 120)
COLOR_TEXT = (255, 255, 255)
FONT       = cv2.FONT_HERSHEY_SIMPLEX


class EmotionDetector:
    """
    Wraps webcam capture, face detection, and PyTorch emotion inference.

    Parameters
    ----------
    on_emotion_change : callable(str) | None
        Triggered whenever the smoothed dominant emotion changes.
    camera_index : int
    show_window  : bool
    """

    def __init__(
        self,
        on_emotion_change: Optional[Callable[[str], None]] = None,
        camera_index: int = 0,
        show_window: bool = True,
    ):
        self.on_emotion_change = on_emotion_change
        self.camera_index      = camera_index
        self.show_window       = show_window

        self._model            = None
        self._device           = None
        self._cap              = None
        self._mtcnn            = None
        self._haar             = None
        self._running          = False

        self._window           = collections.deque(maxlen=MAX_WINDOW_FRAMES)
        self._current_emotion  = None
        self._last_raw_emotion = "—"
        self._last_confidence  = 0.0
        self._current_song_info: Optional[dict] = None

    # ── Model loading ──────────────────────────────────────────────────────────
    def _load_model(self):
        if self._model is not None:
            return

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model not found: {MODEL_PATH}\n"
                "Run  python src/train.py  first."
            )

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[Detect] Loading model from {MODEL_PATH} (device={self._device}) …")

        checkpoint = torch.load(MODEL_PATH, map_location=self._device)
        self._model = EmotionCNN(num_classes=NUM_CLASSES).to(self._device)
        self._model.load_state_dict(checkpoint['model_state'])
        self._model.eval()

        val_acc = checkpoint.get('val_acc', 0)
        print(f"[Detect] Model loaded ✓  (best val_acc={val_acc*100:.2f}%)")

    # ── Face detection ─────────────────────────────────────────────────────────
    def _init_face_detector(self):
        try:
            from facenet_pytorch import MTCNN as FacenetMTCNN
            import torch
            self._mtcnn = FacenetMTCNN(keep_all=True, device='cpu')
            print("[Detect] Face detector: MTCNN (facenet-pytorch) ✓")
        except Exception as e:
            print(f"[Detect] MTCNN unavailable ({e}), falling back to Haar cascade.")
            self._haar = cv2.CascadeClassifier(HAAR_XML)
            if self._haar.empty():
                raise RuntimeError("Haar cascade XML not found.")
            print("[Detect] Face detector: Haar cascade ✓")

    def _detect_faces_mtcnn(self, frame_rgb):
        from PIL import Image
        img = Image.fromarray(frame_rgb)
        boxes, probs = self._mtcnn.detect(img)
        result = []
        if boxes is None:
            return result
        for box, prob in zip(boxes, probs):
            if prob is None or prob < 0.85:
                continue
            x1, y1, x2, y2 = box
            x, y = int(max(0, x1)), int(max(0, y1))
            w, h = int(x2 - x1), int(y2 - y1)
            result.append((x, y, w, h))
        return result

    def _detect_faces_haar(self, frame_gray):
        faces = self._haar.detectMultiScale(
            frame_gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48)
        )
        return [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces] \
               if len(faces) else []

    def detect_faces(self, frame_bgr):
        if self._mtcnn:
            return self._detect_faces_mtcnn(
                cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            )
        return self._detect_faces_haar(
            cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        )

    # ── Emotion inference ──────────────────────────────────────────────────────
    def _infer_emotion(self, face_bgr: np.ndarray):
        """Returns (emotion_label, confidence)."""
        tensor = preprocess_face(face_bgr).to(self._device)  # (1,1,48,48)
        with torch.no_grad():
            logits = self._model(tensor)                       # (1,7)
            probs  = torch.softmax(logits, dim=1)[0].cpu().numpy()
        idx = int(np.argmax(probs))
        return EMOTION_LABELS[idx], float(probs[idx])

    # ── Smoothing ──────────────────────────────────────────────────────────────
    def _update_window(self, label: str) -> Optional[str]:
        self._window.append(label)
        if len(self._window) < 5:
            return None
        dominant = collections.Counter(self._window).most_common(1)[0][0]
        if dominant != self._current_emotion:
            self._current_emotion = dominant
            return dominant
        return None

    # ── OpenCV overlay ─────────────────────────────────────────────────────────
    def _draw_overlay(self, frame, faces, song_info):
        h, w = frame.shape[:2]

        for (fx, fy, fw, fh) in faces:
            cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), COLOR_BOX, 2)
            label  = f"{self._last_raw_emotion}  {self._last_confidence*100:.0f}%"
            text_y = max(fy - 10, 20)
            cv2.putText(frame, label, (fx, text_y),
                        FONT, 0.75, COLOR_BOX, 2, cv2.LINE_AA)

        # Emotion badge — top left
        dominant = self._current_emotion or "Detecting…"
        cv2.rectangle(frame, (0, 0), (300, 38), (20, 20, 20), -1)
        cv2.putText(frame, f"Emotion: {dominant.upper()}", (8, 26),
                    FONT, 0.72, (0, 255, 180), 2, cv2.LINE_AA)

        # Now-playing banner — bottom strip
        if song_info:
            title  = song_info.get("title",  "")
            artist = song_info.get("artist", "")
            lang   = song_info.get("language", "")
            era    = song_info.get("era", "")
            banner = f"  ♪  {title}  —  {artist}  [{lang} / {era}]"
            cv2.rectangle(frame, (0, h-44), (w, h), (15, 15, 15), -1)
            cv2.putText(frame, banner, (8, h-14),
                        FONT, 0.62, (255, 200, 60), 1, cv2.LINE_AA)

        # Quit hint — top right
        cv2.putText(frame, "Press Q to quit", (w-180, 26),
                    FONT, 0.55, (160, 160, 160), 1, cv2.LINE_AA)

        return frame

    # ── Public API ─────────────────────────────────────────────────────────────
    def set_song_info(self, song_info: Optional[dict]):
        self._current_song_info = song_info

    def start(self):
        """Open webcam and run detection loop (blocking)."""
        self._load_model()
        self._init_face_detector()

        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera {self.camera_index}.")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._running  = True
        frame_count    = 0
        cached_faces   = []

        print("[Detect] Webcam loop started. Press Q to quit.")

        try:
            while self._running:
                ret, frame = self._cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

                frame_count += 1

                if frame_count % INFER_EVERY_N_FRAMES == 0:
                    cached_faces = self.detect_faces(frame)

                    if cached_faces:
                        x, y, w, h = max(cached_faces, key=lambda f: f[2]*f[3])
                        fh_img, fw_img = frame.shape[:2]
                        face_crop = frame[y:min(y+h, fh_img), x:min(x+w, fw_img)]

                        if face_crop.size > 0:
                            label, conf = self._infer_emotion(face_crop)
                            self._last_raw_emotion = label
                            self._last_confidence  = conf

                            changed = self._update_window(label)
                            if changed and self.on_emotion_change:
                                self.on_emotion_change(changed)

                frame = self._draw_overlay(frame, cached_faces,
                                           self._current_song_info)

                if self.show_window:
                    cv2.imshow("Emotion Music Player", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord('q'), 27):
                        self._running = False

        finally:
            self.release()

    def stop(self):
        self._running = False

    def release(self):
        if self._cap and self._cap.isOpened():
            self._cap.release()
        if self.show_window:
            cv2.destroyAllWindows()
        print("[Detect] Resources released.")


# ── CLI quick test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    def on_change(emotion):
        print(f"\n[Detect] ★ Emotion → {emotion.upper()}\n")

    EmotionDetector(on_emotion_change=on_change, show_window=True).start()
