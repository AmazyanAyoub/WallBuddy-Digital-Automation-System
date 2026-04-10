import os
import json
import logging

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import MOCKUP_DIR, JPEG_QUALITY, DPI

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mockup_config.json")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_config() -> list[dict]:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)["mockups"]


def _load_image_bgr(path: str) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def _warp_artwork(artwork_path: str, slot: dict, canvas_w: int, canvas_h: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Warps artwork into the 4-corner slot using perspective transform.
    Returns (warped_bgr, mask) both at canvas size.
    """
    tl = slot["top_left"]
    tr = slot["top_right"]
    br = slot["bottom_right"]
    bl = slot["bottom_left"]

    # Estimate artwork dimensions from the slot corners
    w = int(max(
        np.linalg.norm(np.array(tr) - np.array(tl)),
        np.linalg.norm(np.array(br) - np.array(bl))
    ))
    h = int(max(
        np.linalg.norm(np.array(bl) - np.array(tl)),
        np.linalg.norm(np.array(br) - np.array(tr))
    ))

    # Load and resize artwork to fill the slot dimensions
    artwork = _load_image_bgr(artwork_path)
    src_h, src_w = artwork.shape[:2]
    scale = max(w / src_w, h / src_h)
    new_w, new_h = round(src_w * scale), round(src_h * scale)
    artwork = cv2.resize(artwork, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    # Center crop to exact slot dimensions
    x0 = (new_w - w) // 2
    y0 = (new_h - h) // 2
    artwork = artwork[y0:y0 + h, x0:x0 + w]

    # Source corners (flat rectangle of artwork)
    src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])

    # Destination corners (perspective slot in the background)
    dst_pts = np.float32([tl, tr, br, bl])

    # Perspective transform
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(artwork, M, (canvas_w, canvas_h))

    # Create mask of the warped area (white polygon → black everywhere else)
    # Dilate by 2px to cover sub-pixel edge gaps from perspective interpolation
    mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.int32([tl, tr, br, bl]), 255)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)

    return warped, mask


def _composite(background: np.ndarray, warped: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Blends warped artwork onto background using the mask."""
    mask3 = cv2.merge([mask, mask, mask])
    result = np.where(mask3 > 0, warped, background)
    return result


# ── Public entry point ────────────────────────────────────────────────────────

def generate_mockups(set_folder: str, images: list[str], output_base: str) -> list[str]:
    """
    Generates mockup JPGs by warping artwork into pre-defined slot coordinates
    on background JPGs. Fast — no PSD processing at runtime.

    Returns list of written mockup JPG paths.
    """
    set_name  = os.path.basename(set_folder)
    out_dir   = os.path.join(output_base, set_name, "mockups")
    os.makedirs(out_dir, exist_ok=True)

    config    = _load_config()
    written   = []

    for mockup in config:
        idx         = mockup["id"]
        bg_path     = os.path.join(MOCKUP_DIR, mockup["background"])
        slots       = mockup["slots"]

        # Skip mockups with no coordinates defined yet
        if not slots:
            logging.warning(f"[{set_name}] Mockup {idx}: no slots defined — skipping")
            continue

        if not os.path.isfile(bg_path):
            logging.warning(f"[{set_name}] Mockup {idx}: background not found ({bg_path}) — skipping")
            continue

        logging.info(f"[{set_name}] Mockup {idx}/{len(config)}: placing artwork on {mockup['background']}")

        bg      = _load_image_bgr(bg_path)
        canvas  = bg.copy()
        h, w    = bg.shape[:2]

        for slot_idx, slot in enumerate(slots):
            image_path = images[slot_idx % len(images)]
            warped, mask = _warp_artwork(image_path, slot, w, h)
            canvas = _composite(canvas, warped, mask)
            logging.info(f"[{set_name}]   Slot {slot_idx + 1}: placed {os.path.basename(image_path)}")

        # Convert BGR → RGB and save
        result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        pil_img    = Image.fromarray(result_rgb)
        out_path   = os.path.join(out_dir, f"{set_name}_mockup_{idx}.jpg")
        pil_img.save(out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI))
        logging.info(f"[{set_name}] Saved → {os.path.basename(out_path)}")
        written.append(out_path)

    return written
