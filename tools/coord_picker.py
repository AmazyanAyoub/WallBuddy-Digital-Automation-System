"""
Coordinate Picker for set_6 mockup slots.

Run from project root:
    python tools/coord_picker.py

It will open bg_1.jpg → bg_5.jpg, then the cover image.
For each image click the 4 corners of each frame in order:
    Top-Left → Top-Right → Bottom-Right → Bottom-Left

Controls:
    Left-click  : place corner
    Right-click : undo last point
    Q / Esc     : save & quit
"""

import json
import os
import sys

import cv2
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
BG_DIR     = os.path.join("mockups", "set_6")
COVER_DIR  = os.path.join("mockups", "set_6", "cover")
NUM_SLOTS  = 6
OUTPUT     = "set_6_coords.json"

CORNER_NAMES = ["top_left", "top_right", "bottom_right", "bottom_left"]
SLOT_COLOURS = [
    (0,   255,   0),   # slot 1 – green
    (0,   128, 255),   # slot 2 – orange
    (255,   0, 128),   # slot 3 – pink
    (0,   255, 255),   # slot 4 – yellow
    (255, 128,   0),   # slot 5 – sky-blue
    (128,   0, 255),   # slot 6 – violet
]
FONT   = cv2.FONT_HERSHEY_SIMPLEX
MAX_W  = 1400
MAX_H  = 900


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_image(path):
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Cannot read: {path}")
    return img


def fit_to_screen(img):
    h, w = img.shape[:2]
    scale = min(MAX_W / w, MAX_H / h, 1.0)
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img, scale


def draw_state(base, clicks, scale, num_slots):
    canvas = base.copy()
    # group clicks into slots of 4
    for i, (x, y) in enumerate(clicks):
        slot_idx   = i // 4
        corner_idx = i % 4
        col        = SLOT_COLOURS[slot_idx % len(SLOT_COLOURS)]
        cv2.circle(canvas, (x, y), 6, col, -1)
        label = f"S{slot_idx+1} {CORNER_NAMES[corner_idx]}"
        cv2.putText(canvas, label, (x + 8, y - 6), FONT, 0.4, col, 1, cv2.LINE_AA)
        # draw polygon when slot is complete
        if corner_idx == 3:
            pts = np.array(clicks[slot_idx * 4: slot_idx * 4 + 4], dtype=np.int32)
            cv2.polylines(canvas, [pts], True, col, 2, cv2.LINE_AA)
    return canvas


def draw_hud(canvas, image_label, clicks, num_slots):
    done        = len(clicks)
    total       = num_slots * 4
    slot        = done // 4 + 1
    corner_idx  = done % 4
    if done >= total:
        status = "DONE — press any key for next image"
    else:
        status = f"Slot {slot}/{num_slots}  click: {CORNER_NAMES[corner_idx]}"

    lines = [
        f"Image: {image_label}   ({done}/{total} clicks)",
        status,
        "[Left-click] place point   [Right-click] undo   [Q/Esc] save & quit",
    ]
    y = 22
    for line in lines:
        cv2.rectangle(canvas, (4, y - 16), (4 + len(line) * 8, y + 5), (0, 0, 0), -1)
        cv2.putText(canvas, line, (5, y), FONT, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        y += 24


# ── Per-image session ─────────────────────────────────────────────────────────

def collect_clicks(win, img_path, label, num_slots):
    img, scale = fit_to_screen(load_image(img_path))
    clicks     = []   # display coords
    done       = [False]
    quit_flag  = [False]

    def mouse_cb(event, x, y, flags, _):
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(clicks) < num_slots * 4:
                clicks.append((x, y))
            if len(clicks) == num_slots * 4:
                done[0] = True
        elif event == cv2.EVENT_RBUTTONDOWN:
            if clicks:
                clicks.pop()
                done[0] = False
        canvas = draw_state(img, clicks, scale, num_slots)
        draw_hud(canvas, label, clicks, num_slots)
        cv2.imshow(win, canvas)

    cv2.setMouseCallback(win, mouse_cb)
    # initial draw
    canvas = draw_state(img, clicks, scale, num_slots)
    draw_hud(canvas, label, clicks, num_slots)
    cv2.imshow(win, canvas)

    while True:
        key = cv2.waitKey(30) & 0xFF
        if key in (ord('q'), 27):
            quit_flag[0] = True
            break
        if done[0] and key != 255:
            break

    # convert display coords → original image coords
    orig_clicks = [(int(round(x / scale)), int(round(y / scale))) for x, y in clicks]
    return orig_clicks, quit_flag[0]


# ── Build images list ─────────────────────────────────────────────────────────

def find_cover(cover_dir):
    for ext in (".png", ".jpg", ".jpeg"):
        for f in sorted(os.listdir(cover_dir)):
            if f.lower().endswith(ext):
                return os.path.join(cover_dir, f)
    return None


def build_image_list(bg_dir, cover_dir):
    images = []
    for i in range(1, 6):   # bg_1 to bg_5
        for ext in (".jpg", ".jpeg", ".png"):
            p = os.path.join(bg_dir, f"bg_{i}{ext}")
            if os.path.isfile(p):
                images.append(("bg", f"bg_{i}{ext}", p, i))
                break
    cover = find_cover(cover_dir)
    if cover:
        images.append(("cover", os.path.basename(cover), cover, None))
    return images


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    images = build_image_list(BG_DIR, COVER_DIR)
    if not images:
        print("No images found. Check that mockups/set_6/bg_1.jpg … bg_5.jpg exist.")
        sys.exit(1)

    print(f"Found {len(images)} image(s) to annotate:")
    for kind, name, path, _ in images:
        print(f"  [{kind}] {name}")

    WIN = "Coordinate Picker — set_6"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)

    mockups     = []
    cover_slots = None
    aborted     = False

    for kind, name, path, bg_id in images:
        print(f"\nAnnotating: {name}")
        orig_clicks, quit_flag = collect_clicks(WIN, path, name, NUM_SLOTS)

        if quit_flag:
            aborted = True
            break

        # build slot dicts from groups of 4 clicks
        slots = []
        for s in range(NUM_SLOTS):
            base = s * 4
            if base + 3 >= len(orig_clicks):
                break
            slots.append({
                "top_left":     list(orig_clicks[base]),
                "top_right":    list(orig_clicks[base + 1]),
                "bottom_right": list(orig_clicks[base + 2]),
                "bottom_left":  list(orig_clicks[base + 3]),
            })

        if kind == "bg":
            mockups.append({"id": bg_id, "background": name, "slots": slots})
            print(f"  Saved {len(slots)} slot(s) for {name}")
        else:
            cover_slots = slots
            print(f"  Saved {len(slots)} cover slot(s)")

    cv2.destroyAllWindows()

    output = {
        "mockups":     mockups,
        "cover_slots": cover_slots or [],
    }
    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2)

    status = "partial save" if aborted else "complete"
    print(f"\n[{status}] → {OUTPUT}")
    print("Copy 'mockups' and 'cover_slots' into mockup_config.json under the 'set_6' key.")


if __name__ == "__main__":
    main()
