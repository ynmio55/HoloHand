"""HoloHand: real-time gesture-driven camera effects.

Controls:
  Open palm: neon tracking box
  Pinch thumb + index: toggle negative filter (hold ~0.55s)
  Fist: spotlight mode
  Peace sign: edge vision
  Q / Escape: exit; M: mirror; S: save screenshot; R: reset
"""
from __future__ import annotations

import argparse
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def raised_fingers(points) -> list[bool]:
    # Wrist and joints are in normalized coordinates. Compare tip to PIP, with
    # a modest distance tolerance to avoid flicker near partially bent fingers.
    return [points[t].y < points[p].y - 0.025 for t, p in ((8, 6), (12, 10), (16, 14), (20, 18))]


def gesture(points) -> str:
    fingers = raised_fingers(points)
    palm_width = max(0.015, np.hypot(points[5].x - points[17].x, points[5].y - points[17].y))
    pinch = np.hypot(points[4].x - points[8].x, points[4].y - points[8].y) / palm_width
    if pinch < 0.36:
        return "PINCH"
    if all(fingers):
        return "OPEN PALM"
    if fingers == [True, True, False, False]:
        return "PEACE"
    if not any(fingers):
        return "FIST"
    return "TRACKING"


class HoldTrigger:
    def __init__(self, hold_seconds: float = 0.55):
        self.hold_seconds = hold_seconds
        self.start: float | None = None
        self.fired = False

    def update(self, active: bool, now: float) -> bool:
        if not active:
            self.start = None
            self.fired = False
            return False
        if self.start is None:
            self.start = now
        if not self.fired and now - self.start >= self.hold_seconds:
            self.fired = True
            return True
        return False


def neon_box(image: np.ndarray, rect: tuple[int, int, int, int], color=(80, 255, 95)) -> None:
    x1, y1, x2, y2 = rect
    overlay = image.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 9, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.20, image, 0.80, 0, dst=image)
    length = max(15, min(35, (x2 - x1) // 5))
    for x, direction in ((x1, 1), (x2, -1)):
        for y, vertical in ((y1, 1), (y2, -1)):
            cv2.line(image, (x, y), (x + direction * length, y), color, 3, cv2.LINE_AA)
            cv2.line(image, (x, y), (x, y + vertical * length), color, 3, cv2.LINE_AA)


def hud(image: np.ndarray, gesture_name: str, mode: str, fps: float, mirror: bool) -> None:
    height, width = image.shape[:2]
    layer = image.copy()
    cv2.rectangle(layer, (0, 0), (width, 78), (12, 18, 15), -1)
    cv2.rectangle(layer, (0, height - 45), (width, height), (12, 18, 15), -1)
    cv2.addWeighted(layer, 0.72, image, 0.28, 0, dst=image)
    cv2.putText(image, "HOLOHAND  /  VISION SYSTEM", (18, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.64, (110, 255, 135), 2, cv2.LINE_AA)
    cv2.putText(image, f"GESTURE: {gesture_name}    EFFECT: {mode}", (18, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (235, 245, 235), 1, cv2.LINE_AA)
    cv2.putText(image, "PINCH: NEGATIVE  |  FIST: SPOTLIGHT  |  PEACE: EDGES", (18, height - 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (205, 228, 205), 1, cv2.LINE_AA)
    cv2.putText(image, f"{fps:4.0f} FPS", (max(10, width - 110), 27), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (110, 255, 135), 1, cv2.LINE_AA)
    if not mirror:
        cv2.putText(image, "UNMIRRORED", (max(10, width - 125), 56), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (215, 230, 215), 1, cv2.LINE_AA)


def apply_spotlight(image: np.ndarray, center: tuple[int, int], radius: int) -> np.ndarray:
    height, width = image.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.circle(mask, center, radius, 255, -1, cv2.LINE_AA)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=max(12, radius // 5))
    dark = (image.astype(np.float32) * 0.14).astype(np.uint8)
    alpha = (mask.astype(np.float32) / 255.0)[:, :, None]
    return np.clip(image * alpha + dark * (1.0 - alpha), 0, 255).astype(np.uint8)


def run(camera: int, width: int, height: int, max_hands: int) -> None:
    cap = cv2.VideoCapture(camera)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {camera}. Check webcam permissions or try --camera 1.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    hands_api = mp.solutions.hands
    draw_api = mp.solutions.drawing_utils
    hold = HoldTrigger()
    negative = False
    mirrored = True
    smoothing: dict[int, np.ndarray] = {}
    frame_times: deque[float] = deque(maxlen=20)
    Path("screenshots").mkdir(exist_ok=True)
    try:
        with hands_api.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            model_complexity=1,
            min_detection_confidence=0.65,
            min_tracking_confidence=0.60,
        ) as hands:
            while True:
                ok, frame = cap.read()
                if not ok:
                    print("Camera frame unavailable. Exiting.")
                    break
                frame = cv2.flip(frame, 1) if mirrored else frame
                h, w = frame.shape[:2]
                now = time.monotonic()
                frame_times.append(now)
                fps = (len(frame_times) - 1) / max(0.001, frame_times[-1] - frame_times[0]) if len(frame_times) > 1 else 0.0
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb.flags.writeable = False
                result = hands.process(rgb)

                primary = "NO HAND"
                mode = "NEGATIVE" if negative else "NORMAL"
                hands_found = result.multi_hand_landmarks or []
                points_per_hand = [entry.landmark for entry in hands_found]
                if points_per_hand:
                    primary = gesture(points_per_hand[0])
                if hold.update(primary == "PINCH", now):
                    negative = not negative
                if negative:
                    frame = cv2.bitwise_not(frame)
                    mode = "NEGATIVE"
                if primary == "PEACE":
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    edges = cv2.Canny(gray, 80, 160)
                    frame = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
                    frame[:, :, 1] = edges
                    mode = "EDGE VISION"
                elif primary == "FIST" and points_per_hand:
                    pt = points_per_hand[0][9]
                    center = (int(clamp(pt.x, 0, 1) * w), int(clamp(pt.y, 0, 1) * h))
                    frame = apply_spotlight(frame, center, max(65, min(w, h) // 5))
                    mode = "SPOTLIGHT"

                stale = set(smoothing)
                for index, hand in enumerate(hands_found):
                    coords = np.array([(p.x * w, p.y * h) for p in hand.landmark])
                    min_xy = coords.min(axis=0)
                    max_xy = coords.max(axis=0)
                    pad = max(12, int(max(max_xy - min_xy) * 0.20))
                    target = np.array([
                        max(0, min_xy[0] - pad), max(0, min_xy[1] - pad),
                        min(w - 1, max_xy[0] + pad), min(h - 1, max_xy[1] + pad)
                    ])
                    previous = smoothing.get(index)
                    smooth = target if previous is None else previous * 0.65 + target * 0.35
                    smoothing[index] = smooth
                    stale.discard(index)
                    rect = tuple(int(v) for v in smooth)
                    neon_box(frame, rect)
                    draw_api.draw_landmarks(
                        frame, hand, hands_api.HAND_CONNECTIONS,
                        draw_api.DrawingSpec(color=(80, 255, 95), thickness=2, circle_radius=2),
                        draw_api.DrawingSpec(color=(65, 150, 65), thickness=1),
                    )
                for index in stale:
                    smoothing.pop(index, None)
                hud(frame, primary, mode, fps, mirrored)
                cv2.imshow("HoloHand - Real-Time Gesture Vision", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
                if key == ord("m"):
                    mirrored = not mirrored
                    smoothing.clear()
                elif key == ord("r"):
                    negative = False
                elif key == ord("s"):
                    filename = Path("screenshots") / f"holohand_{datetime.now():%Y%m%d_%H%M%S}.png"
                    cv2.imwrite(str(filename), frame)
                    print(f"Saved {filename}")
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HoloHand camera gesture vision")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--max-hands", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    try:
        run(args.camera, args.width, args.height, args.max_hands)
    except (RuntimeError, KeyboardInterrupt) as exc:
        print(f"HoloHand stopped: {exc}")
