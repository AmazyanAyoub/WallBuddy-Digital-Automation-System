"""
Mockup Calibration Tool
-----------------------
Click exactly on the 4 corners of the frame in each background image.
Click order: Top-Left → Top-Right → Bottom-Right → Bottom-Left

Controls:
  Left click  → place a point
  Z           → undo last point
  R           → restart current image
  S           → save and move to next image (only when all 4 points placed)
  Q           → quit without saving remaining

Results are saved directly to mockup_config.json.
"""

import os
import json
import cv2
import numpy as np

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
MOCKUP_DIR  = os.path.join(BASE_DIR, "mockups")
CONFIG_PATH = os.path.join(BASE_DIR, "mockup_config.json")

POINT_LABELS = ["Top-Left", "Top-Right", "Bottom-Right", "Bottom-Left"]
COLORS       = [(0, 255, 0), (0, 200, 255), (0, 0, 255), (255, 0, 255)]

# Images to calibrate: (config_key, label, image_path)
TARGETS = [
    ("mockup_1", "bg_1 — Mockup 1", os.path.join(MOCKUP_DIR, "bg_1.jpg")),
    ("mockup_2", "bg_2 — Mockup 2", os.path.join(MOCKUP_DIR, "bg_2.jpg")),
    ("mockup_3", "bg_3 — Mockup 3", os.path.join(MOCKUP_DIR, "bg_3.jpg")),
    ("mockup_4", "bg_4 — Mockup 4", os.path.join(MOCKUP_DIR, "bg_4.jpg")),
    ("mockup_5", "bg_5 — Mockup 5", os.path.join(MOCKUP_DIR, "bg_5.jpg")),
    ("cover",    "COVER_1 — Cover slot", os.path.join(MOCKUP_DIR, "cover", "COVER_1.png")),
]


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  Saved to {CONFIG_PATH}")


def draw_state(base_img: np.ndarray, points: list, label: str) -> np.ndarray:
    img = base_img.copy()
    h, w = img.shape[:2]

    # Instructions top bar
    cv2.rectangle(img, (0, 0), (w, 60), (30, 30, 30), -1)
    cv2.putText(img, label, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    next_idx = len(points)
    if next_idx < 4:
        hint = f"Click {POINT_LABELS[next_idx]}  |  Z=undo  R=restart  Q=quit"
    else:
        hint = "All 4 points set — press S to save and continue  |  Z=undo  R=restart"
    cv2.putText(img, hint, (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

    # Draw placed points
    for i, (x, y) in enumerate(points):
        color = COLORS[i]
        cv2.circle(img, (x, y), 6, color, -1)
        cv2.circle(img, (x, y), 8, (255, 255, 255), 1)
        cv2.putText(img, POINT_LABELS[i], (x + 10, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    # Draw polygon when all 4 points are placed
    if len(points) == 4:
        pts = np.array(points, dtype=np.int32)
        cv2.polylines(img, [pts], isClosed=True, color=(0, 255, 255), thickness=2)

    return img


def calibrate_image(label: str, img_path: str) -> list | None:
    """
    Opens the image, lets user click 4 corners.
    Returns [top_left, top_right, bottom_right, bottom_left] or None if quit.
    """
    base_img = cv2.imdecode(
        np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if base_img is None:
        print(f"  ERROR: Could not load {img_path} — skipping")
        return []

    points   = []
    result   = {"done": False, "quit": False}
    win_name = "Mockup Calibration"

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append((x, y))
            print(f"  [{len(points)}/4] {POINT_LABELS[len(points)-1]}: ({x}, {y})")

    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 900, 700)
    cv2.setMouseCallback(win_name, on_click)

    print(f"\n>>> {label}")
    print(f"    Click: TL → TR → BR → BL  then press S to save")

    while True:
        frame = draw_state(base_img, points, label)
        cv2.imshow(win_name, frame)
        key = cv2.waitKey(20) & 0xFF

        if key == ord("z") and points:          # undo
            removed = points.pop()
            print(f"  Undo: removed {removed}")

        elif key == ord("r"):                   # restart
            points.clear()
            print(f"  Restarted — click again from Top-Left")

        elif key == ord("s") and len(points) == 4:  # save
            result["done"] = True
            break

        elif key == ord("q"):                   # quit
            result["quit"] = True
            break

    cv2.destroyAllWindows()

    if result["quit"]:
        return None
    return points


def main():
    config = load_config()

    for key, label, img_path in TARGETS:
        if not os.path.isfile(img_path):
            print(f"\nSkipping {label} — file not found: {img_path}")
            continue

        points = calibrate_image(label, img_path)

        if points is None:
            print("\nQuit — remaining images not calibrated.")
            break

        if not points:
            continue

        tl, tr, br, bl = points
        slot = {
            "top_left":     list(tl),
            "top_right":    list(tr),
            "bottom_right": list(br),
            "bottom_left":  list(bl),
        }

        if key == "cover":
            config["cover_slot"] = slot
            print(f"  Cover slot updated: {slot}")
        else:
            idx = int(key.split("_")[1]) - 1
            config["mockups"][idx]["slots"][0] = slot
            print(f"  Mockup {idx+1} slot updated: {slot}")

        save_config(config)

    print("\nCalibration complete.")


if __name__ == "__main__":
    main()
