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

    # Resize artwork to exactly the slot dimensions
    artwork = _load_image_bgr(artwork_path)
    artwork = cv2.resize(artwork, (w, h), interpolation=cv2.INTER_LANCZOS4)

    # Source corners (flat rectangle of artwork)
    src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])

    # Destination corners (perspective slot in the background)
    dst_pts = np.float32([tl, tr, br, bl])

    # Perspective transform
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(artwork, M, (canvas_w, canvas_h))

    # Create mask of the warped area
    mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.int32([tl, tr, br, bl]), 255)

    return warped, mask


def _composite(background: np.ndarray, warped: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Blends warped artwork onto background using the mask."""
    mask3 = cv2.merge([mask, mask, mask])
    result = np.where(mask3 > 0, warped, background)
    return result


# ── Public entry point ────────────────────────────────────────────────────────

def generate_mockups(set_folder: str, images: list[str], output_base: str) -> list[str]:
    """
    Generates mockup JPGs for every image in the set.
    Each image gets all 5 mockups saved in its own subfolder (Print_1, Print_2, ...).

    Output structure:
        output_base/set_name/mockups/Print_1/set_name_mockup_1.jpg ... _mockup_5.jpg
        output_base/set_name/mockups/Print_2/...

    Returns list of all written mockup JPG paths.
    """
    set_name  = os.path.basename(set_folder)
    config    = _load_config()
    written   = []

    for img_idx, image_path in enumerate(images, start=1):
        print_label = f"Print_{img_idx}"
        out_dir     = os.path.join(output_base, set_name, "mockups", print_label)
        os.makedirs(out_dir, exist_ok=True)

        logging.info(f"[{set_name}] {print_label}: generating mockups for {os.path.basename(image_path)}")

        for mockup in config:
            idx     = mockup["id"]
            bg_path = os.path.join(MOCKUP_DIR, mockup["background"])
            slots   = mockup["slots"]

            # Skip mockups with no coordinates defined yet
            if not slots:
                logging.warning(f"[{set_name}] Mockup {idx}: no slots defined — skipping")
                continue

            if not os.path.isfile(bg_path):
                logging.warning(f"[{set_name}] Mockup {idx}: background not found ({bg_path}) — skipping")
                continue

            bg     = _load_image_bgr(bg_path)
            canvas = bg.copy()
            h, w   = bg.shape[:2]

            for slot_idx, slot in enumerate(slots):
                warped, mask = _warp_artwork(image_path, slot, w, h)
                canvas = _composite(canvas, warped, mask)

            result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            pil_img    = Image.fromarray(result_rgb)
            out_path   = os.path.join(out_dir, f"{set_name}_mockup_{idx}.jpg")
            pil_img.save(out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI))
            logging.info(f"[{set_name}]   {print_label} → mockup_{idx}.jpg saved")
            written.append(out_path)

    return written
