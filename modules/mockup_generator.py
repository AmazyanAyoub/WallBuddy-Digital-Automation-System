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
COVER_DIR   = None  # set dynamically per job_type inside generate_mockups


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_config(job_type: str) -> dict:
    with open(CONFIG_PATH, "r") as f:
        full = json.load(f)
    if job_type not in full:
        raise ValueError(f"No config section found for job_type='{job_type}'")
    return full[job_type]


def _load_image_bgr(path: str) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def _place_artwork(canvas: np.ndarray, artwork_path: str, slot: dict) -> None:
    tl = slot["top_left"]
    tr = slot["top_right"]
    br = slot["bottom_right"]
    bl = slot["bottom_left"]

    canvas_h, canvas_w = canvas.shape[:2]
    SCALE = 4

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
    dst_pts = np.float32([tl, tr, br, bl]) * SCALE

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped_big = cv2.warpPerspective(artwork, M, (canvas_w * SCALE, canvas_h * SCALE))

    mask_big = np.zeros((canvas_h * SCALE, canvas_w * SCALE), dtype=np.uint8)
    cv2.fillPoly(mask_big, [dst_pts.astype(np.int32)], 255, lineType=cv2.LINE_AA)

    warped = cv2.resize(warped_big, (canvas_w, canvas_h), interpolation=cv2.INTER_AREA)
    mask   = cv2.resize(mask_big,   (canvas_w, canvas_h), interpolation=cv2.INTER_AREA)

    mask = cv2.GaussianBlur(mask, (3, 3), 0.75)

    alpha = mask.astype(np.float32) / 255.0
    alpha_3ch = cv2.merge([alpha, alpha, alpha])
    canvas[:] = (warped.astype(np.float32) * alpha_3ch +
                 canvas.astype(np.float32) * (1.0 - alpha_3ch)).astype(np.uint8)


# ── Public entry point ────────────────────────────────────────────────────────

def generate_mockups(
    set_folder: str,
    images: list[str],
    output_base: str,
    atca_id: int,
    job_type: str = "single",
) -> list[str]:
    """
    Generates mockup JPGs for the job.

    job_type="single": one image per mockup, 7 mockups total (5 room + bg_6 as-is + cover)
    job_type="set_3":  3 images placed into 3 slots per mockup background

    Backgrounds are loaded from: MOCKUP_DIR/{job_type}/bg_N.jpg
    Config section is loaded from mockup_config.json under the job_type key.

    Returns list of all written mockup JPG paths.
    """
    atca_name     = f"ATCA_{atca_id:04d}"
    config        = _load_config(job_type)
    mockup_cfg    = config["mockups"]
    mockup_bg_dir = os.path.join(MOCKUP_DIR, job_type)
    cover_dir     = os.path.join(MOCKUP_DIR, job_type, "cover")

    out_dir = os.path.join(output_base, atca_name, "mockups")
    os.makedirs(out_dir, exist_ok=True)

    written = []

    if job_type == "single":
        _generate_single(
            images=images,
            mockup_cfg=mockup_cfg,
            mockup_bg_dir=mockup_bg_dir,
            cover_slot=config["cover_slot"],
            cover_dir=cover_dir,
            out_dir=out_dir,
            atca_name=atca_name,
            written=written,
        )
    elif job_type == "set_3":
        _generate_set3(
            images=images,
            mockup_cfg=mockup_cfg,
            mockup_bg_dir=mockup_bg_dir,
            cover_slots=config["cover_slots"],
            cover_dir=cover_dir,
            out_dir=out_dir,
            atca_name=atca_name,
            written=written,
        )
    
    elif job_type == "set_4":
        _generate_set4(
            images=images,
            mockup_cfg=mockup_cfg,
            mockup_bg_dir=mockup_bg_dir,
            cover_slots=config["cover_slots"],
            cover_dir=cover_dir,
            out_dir=out_dir,
            atca_name=atca_name,
            written=written,
        )
    elif job_type == "set_6":
        _generate_set6(
            images=images,
            mockup_cfg=mockup_cfg,
            mockup_bg_dir=mockup_bg_dir,
            cover_slots=config["cover_slots"],
            cover_dir=cover_dir,
            out_dir=out_dir,
            atca_name=atca_name,
            written=written,
        )
    return written


# ── Single image mockup logic ─────────────────────────────────────────────────

def _generate_single(
    images, mockup_cfg, mockup_bg_dir, cover_slot, cover_dir,
    out_dir, atca_name, written
):
    for img_idx, image_path in enumerate(images, start=1):
        img_prefix = atca_name if len(images) == 1 else f"{atca_name}_{img_idx}"
        logging.info(f"[{atca_name}] generating mockups for {os.path.basename(image_path)}")

        # Mockups 1-5: room scenes
        for mockup in mockup_cfg:
            idx     = mockup["id"]
            bg_path = os.path.join(mockup_bg_dir, mockup["background"])
            slots   = mockup["slots"]

            if not slots:
                logging.warning(f"[{atca_name}] Mockup {idx}: no slots defined — skipping")
                continue
            if not os.path.isfile(bg_path):
                logging.warning(f"[{atca_name}] Mockup {idx}: background not found ({bg_path}) — skipping")
                continue

            canvas = _load_image_bgr(bg_path)
            for slot in slots:
                _place_artwork(canvas, image_path, slot)

            result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            out_path   = os.path.join(out_dir, f"{img_prefix}_mockup_{idx}.jpg")
            Image.fromarray(result_rgb).save(out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI))
            logging.info(f"[{atca_name}]   mockup_{idx}.jpg saved")
            written.append(out_path)

        # Mockup 6: bg_6 as-is
        bg6_path = os.path.join(mockup_bg_dir, "bg_6.jpg")
        if os.path.isfile(bg6_path):
            bg6 = _load_image_bgr(bg6_path)
            out_path = os.path.join(out_dir, f"{img_prefix}_mockup_6.jpg")
            Image.fromarray(cv2.cvtColor(bg6, cv2.COLOR_BGR2RGB)).save(
                out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI)
            )
            logging.info(f"[{atca_name}]   mockup_6.jpg saved (bg_6 as-is)")
            written.append(out_path)
        else:
            logging.warning(f"[{atca_name}] bg_6.png not found — skipping mockup 6")

        # Mockup 7: cycling cover
        cover_idx  = get_next_cover(job_type="single")
        cover_path = os.path.join(cover_dir, f"COVER_{cover_idx}.png")
        if not os.path.isfile(cover_path):
            cover_path = os.path.join(cover_dir, f"COVER_{cover_idx}.jpg")
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


# ── Set-3 mockup logic ────────────────────────────────────────────────────────

def _generate_set3(images, mockup_cfg, mockup_bg_dir, cover_slots, cover_dir, out_dir, atca_name, written):
    """
    Each mockup background has 3 slots — one per image in the group.
    All 3 images are composited onto the same canvas per background.
    """
    for mockup in mockup_cfg:
        idx     = mockup["id"]
        bg_path = os.path.join(mockup_bg_dir, mockup["background"])
        slots   = mockup["slots"]

        if len(slots) < 3:
            logging.warning(f"[{atca_name}] set_3 mockup {idx}: needs 3 slots, found {len(slots)} — skipping")
            continue
        if not os.path.isfile(bg_path):
            logging.warning(f"[{atca_name}] set_3 mockup {idx}: background not found ({bg_path}) — skipping")
            continue

        canvas = _load_image_bgr(bg_path)
        for img_path, slot in zip(images, slots):
            _place_artwork(canvas, img_path, slot)

        result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        out_path   = os.path.join(out_dir, f"{atca_name}_mockup_{idx}.jpg")
        Image.fromarray(result_rgb).save(out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI))
        logging.info(f"[{atca_name}]   set_3 mockup_{idx}.jpg saved")
        written.append(out_path)

    # bg_6 as-is
    bg6_path = os.path.join(mockup_bg_dir, "bg_6.jpg")
    if os.path.isfile(bg6_path):
        bg6 = _load_image_bgr(bg6_path)
        out_path = os.path.join(out_dir, f"{atca_name}_mockup_6.jpg")
        Image.fromarray(cv2.cvtColor(bg6, cv2.COLOR_BGR2RGB)).save(
            out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI)
        )
        logging.info(f"[{atca_name}]   set_3 mockup_6.jpg saved (bg_6 as-is)")
        written.append(out_path)
    else:
        logging.warning(f"[{atca_name}] set_3 bg_6.jpg not found — skipping mockup 6")

    # Cover mockup: 3 images placed into 3 cover slots
    cover_idx  = get_next_cover(job_type="set_3")
    cover_path = os.path.join(cover_dir, f"COVER_{cover_idx}.png")
    if not os.path.isfile(cover_path):
        cover_path = os.path.join(cover_dir, f"COVER_{cover_idx}.jpg")
    if os.path.isfile(cover_path):
        canvas = _load_image_bgr(cover_path)
        for img_path, slot in zip(images, cover_slots):
            _place_artwork(canvas, img_path, slot)
        result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        out_path   = os.path.join(out_dir, f"{atca_name}_mockup_cover.jpg")
        Image.fromarray(result_rgb).save(out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI))
        logging.info(f"[{atca_name}]   set_3 mockup_cover.jpg saved (cover {cover_idx}.png)")
        written.append(out_path)
    else:
        logging.warning(f"[{atca_name}] cover/{cover_idx}.png not found — skipping cover mockup")



def _generate_set4(images, mockup_cfg, mockup_bg_dir, cover_slots, cover_dir, out_dir, atca_name, written):
    """
    Each mockup background has 4 slots — one per image in the group.
    All 4 images are composited onto the same canvas per background.
    """

    for mockup in mockup_cfg:
        idx     = mockup["id"]
        bg_path = os.path.join(mockup_bg_dir, mockup["background"])
        slots   = mockup["slots"]

        if len(slots) < 4:
            logging.warning(f"[{atca_name}] set_4 mockup {idx}: needs 4 slots, found {len(slots)} — skipping")
            continue
        if not os.path.isfile(bg_path):
            logging.warning(f"[{atca_name}] set_4 mockup {idx}: background not found ({bg_path}) — skipping")
            continue

        canvas = _load_image_bgr(bg_path)
        for img_path, slot in zip(images, slots):
            _place_artwork(canvas, img_path, slot)

        result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        out_path   = os.path.join(out_dir, f"{atca_name}_mockup_{idx}.jpg")
        Image.fromarray(result_rgb).save(out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI))
        logging.info(f"[{atca_name}]   set_4 mockup_{idx}.jpg saved")
        written.append(out_path)

    # bg_6 as-is
    bg6_path = os.path.join(mockup_bg_dir, "bg_6.jpg")
    if os.path.isfile(bg6_path):
        bg6 = _load_image_bgr(bg6_path)
        out_path = os.path.join(out_dir, f"{atca_name}_mockup_6.jpg")
        Image.fromarray(cv2.cvtColor(bg6, cv2.COLOR_BGR2RGB)).save(
            out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI)
        )
        logging.info(f"[{atca_name}]   set_4 mockup_6.jpg saved (bg_6 as-is)")
        written.append(out_path)
    else:
        logging.warning(f"[{atca_name}] set_4 bg_6.jpg not found — skipping mockup 6")

    cover_idx  = get_next_cover(job_type="set_4")
    cover_path = os.path.join(cover_dir, f"COVER_{cover_idx}.png")
    if not os.path.isfile(cover_path):
        cover_path = os.path.join(cover_dir, f"COVER_{cover_idx}.jpg")
    if os.path.isfile(cover_path):
        canvas = _load_image_bgr(cover_path)
        for img_path, slot in zip(images, cover_slots):
            _place_artwork(canvas, img_path, slot)
        result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        out_path   = os.path.join(out_dir, f"{atca_name}_mockup_cover.jpg")
        Image.fromarray(result_rgb).save(out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI))
        logging.info(f"[{atca_name}]   set_4 mockup_cover.jpg saved (cover {cover_idx}.png)")
        written.append(out_path)
    else:
        logging.warning(f"[{atca_name}] cover/{cover_idx}.png not found — skipping cover mockup")


def _generate_set6(images, mockup_cfg, mockup_bg_dir, cover_slots, cover_dir, out_dir, atca_name, written):
    """
    Each mockup background has 6 slots — one per image in the group.
    All 6 images are composited onto the same canvas per background.
    """

    for mockup in mockup_cfg:
        idx     = mockup["id"]
        bg_path = os.path.join(mockup_bg_dir, mockup["background"])
        slots   = mockup["slots"]

        if len(slots) < 6:
            logging.warning(f"[{atca_name}] set_6 mockup {idx}: needs 6 slots, found {len(slots)} — skipping")
            continue
        if not os.path.isfile(bg_path):
            logging.warning(f"[{atca_name}] set_6 mockup {idx}: background not found ({bg_path}) — skipping")
            continue

        canvas = _load_image_bgr(bg_path)
        for img_path, slot in zip(images, slots):
            _place_artwork(canvas, img_path, slot)

        result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        out_path   = os.path.join(out_dir, f"{atca_name}_mockup_{idx}.jpg")
        Image.fromarray(result_rgb).save(out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI))
        logging.info(f"[{atca_name}]   set_6 mockup_{idx}.jpg saved")
        written.append(out_path)

    bg_6_path = os.path.join(mockup_bg_dir, "bg_6.jpg")
    if os.path.isfile(bg_6_path):
        bg_6 = _load_image_bgr(bg_6_path)
        out_path = os.path.join(out_dir, f"{atca_name}_mockup_6.jpg")
        Image.fromarray(cv2.cvtColor(bg_6, cv2.COLOR_BGR2RGB)).save(
            out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI)
        )
        logging.info(f"[{atca_name}]   set_6 mockup_6.jpg saved (bg_6 as-is)")
        written.append(out_path)
    else:
        logging.warning(f"[{atca_name}] set_6 bg_6.jpg not found — skipping mockup 6")

    
    cover_idx  = get_next_cover(job_type="set_6")
    cover_path = os.path.join(cover_dir, f"COVER_{cover_idx}.png")
    if not os.path.isfile(cover_path):
        cover_path = os.path.join(cover_dir, f"COVER_{cover_idx}.jpg")
    if os.path.isfile(cover_path):
        canvas = _load_image_bgr(cover_path)
        for img_path, slot in zip(images, cover_slots):
            _place_artwork(canvas, img_path, slot)
        result_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        out_path   = os.path.join(out_dir, f"{atca_name}_mockup_cover.jpg")
        Image.fromarray(result_rgb).save(out_path, format="JPEG", quality=JPEG_QUALITY, dpi=(DPI, DPI))
        logging.info(f"[{atca_name}]   set_6 mockup_cover.jpg saved (cover {cover_idx}.png)")
        written.append(out_path)
    else:
        logging.warning(f"[{atca_name}] cover/{cover_idx}.png not found — skipping cover mockup")