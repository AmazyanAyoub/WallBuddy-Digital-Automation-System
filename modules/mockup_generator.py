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
from utils.cover_index import get_and_increment as get_next_cover

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mockup_config.json")
COVER_DIR   = os.path.join(MOCKUP_DIR, "cover")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def _load_image_bgr(path: str) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def _place_artwork(canvas: np.ndarray, artwork_path: str, slot: dict) -> None:
    """
    Warps artwork into the slot directly onto the canvas using BORDER_TRANSPARENT.
    No mask, no compositing — zero edge artifacts.
    Modifies canvas in place.
    """
    tl = slot["top_left"]
    tr = slot["top_right"]
    br = slot["bottom_right"]
    bl = slot["bottom_left"]

    canvas_h, canvas_w = canvas.shape[:2]

    w = int(max(
        np.linalg.norm(np.array(tr) - np.array(tl)),
        np.linalg.norm(np.array(br) - np.array(bl))
    ))
    h = int(max(
        np.linalg.norm(np.array(bl) - np.array(tl)),
        np.linalg.norm(np.array(br) - np.array(tr))
    ))

    artwork = _load_image_bgr(artwork_path)
    artwork = cv2.resize(artwork, (w, h), interpolation=cv2.INTER_LANCZOS4)

    src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst_pts = np.float32([tl, tr, br, bl])

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    cv2.warpPerspective(artwork, M, (canvas_w, canvas_h),
                        dst=canvas, borderMode=cv2.BORDER_TRANSPARENT)


# ── Public entry point ────────────────────────────────────────────────────────

def generate_mockups(set_folder: str, images: list[str], output_base: str, atca_id: int) -> list[str]:
    """
    Generates mockup JPGs for every image in the set.
    Each image gets all 5 mockups saved in its own subfolder (Print_1, Print_2, ...).

    Output structure:
        output_base/ATCA_000{id}/mockups/Print_1/...mockup_1.jpg
        output_base/ATCA_000{id}/mockups/Print_2/...

    Returns list of all written mockup JPG paths.
    """
    set_name  = os.path.basename(set_folder)
    atca_name = f"ATCA_{atca_id:04d}"
    config    = _load_config()
    mockups   = config["mockups"]
    cover_slot = config["cover_slot"]
    written   = []

    out_dir = os.path.join(output_base, atca_name, "mockups")
    os.makedirs(out_dir, exist_ok=True)

    for img_idx, image_path in enumerate(images, start=1):
        img_prefix = atca_name if len(images) == 1 else f"{atca_name}_{img_idx}"
        logging.info(f"[{atca_name}] generating mockups for {os.path.basename(image_path)}")

        # ── Mockups 1-5: room scenes with artwork warped in ───────────────────
        for mockup in mockups:
            idx     = mockup["id"]
            bg_path = os.path.join(MOCKUP_DIR, mockup["background"])
            slots   = mockup["slots"]

            if not slots:
                logging.warning(f"[{atca_name}] Mockup {idx}: no slots defined — skipping")
                continue

            if not os.path.isfile(bg_path):
                logging.warning(f"[{atca_name}] Mockup {idx}: background not found — skipping")
                continue

            canvas = _load_image_bgr(bg_path)
            for slot in slots:
                _place_artwork(canvas, image_path, slot)

            result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            out_path   = os.path.join(out_dir, f"{img_prefix}_mockup_{idx}.jpg")
            Image.fromarray(result_rgb).save(out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI))
            logging.info(f"[{atca_name}]   mockup_{idx}.jpg saved")
            written.append(out_path)

        # ── Mockup 6: bg_6 saved as-is, no artwork placed ────────────────────
        bg6_path = os.path.join(MOCKUP_DIR, "bg_6.png")
        if os.path.isfile(bg6_path):
            bg6 = _load_image_bgr(bg6_path)
            out_path = os.path.join(out_dir, f"{img_prefix}_mockup_6.jpg")
            Image.fromarray(cv2.cvtColor(bg6, cv2.COLOR_BGR2RGB)).save(
                out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI)
            )
            logging.info(f"[{atca_name}]   mockup_6.jpg saved (bg_6 as-is)")
            written.append(out_path)
        else:
            logging.warning(f"[{atca_name}] bg_6.jpg not found — skipping mockup 6")

        # ── Mockup 7: cover PNG with artwork placed, cycling color ────────────
        cover_idx  = get_next_cover()
        cover_path = os.path.join(COVER_DIR, f"COVER_{cover_idx}.png")
        if os.path.isfile(cover_path):
            canvas = _load_image_bgr(cover_path)
            _place_artwork(canvas, image_path, cover_slot)
            result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            out_path   = os.path.join(out_dir, f"{img_prefix}_mockup_7.jpg")
            Image.fromarray(result_rgb).save(out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI))
            logging.info(f"[{atca_name}]   mockup_7.jpg saved (cover {cover_idx}.png)")
            written.append(out_path)
        else:
            logging.warning(f"[{atca_name}] cover/{cover_idx}.png not found — skipping mockup 7")

    return written
