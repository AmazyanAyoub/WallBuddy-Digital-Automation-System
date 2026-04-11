import os
import sys
import logging
import types

import cv2
import numpy as np
import torch
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import (
    UPSCALE_THRESHOLD,
    WEIGHTS_4X,
    WEIGHTS_2X,
    JPEG_QUALITY,
    DPI,
    PRINT_FORMATS,
    IMAGE_EXTENSIONS,
)


# ── 1. Image discovery ────────────────────────────────────────────────────────

def get_images_in_set(set_folder: str) -> list[str]:
    """
    Returns sorted list of image paths found in set_folder.
    Sorted alphabetically so image1 → Print_1, image2 → Print_2, etc.
    """
    images = []
    for entry in sorted(os.scandir(set_folder), key=lambda e: e.name.lower()):
        if not entry.is_file():
            continue
        ext = os.path.splitext(entry.name)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            images.append(entry.path)
    return images


# ── 2. Size detection ─────────────────────────────────────────────────────────

def needs_upscale(image_path: str) -> tuple[bool, int]:
    """
    Opens image, reads dimensions, returns (should_upscale, longest_side).
    """
    with Image.open(image_path) as img:
        w, h = img.size
    longest = max(w, h)
    return longest < UPSCALE_THRESHOLD, longest


# ── 3. Upscaling (adapted from Rory/src/upscale.py) ──────────────────────────

def _load_realesrgan():
    """
    Lazy-loads Real-ESRGAN models. Applies torchvision compatibility shim
    for older torchvision versions that lack functional_tensor module.
    Returns (upsampler_4x, upsampler_2x).
    """
    # Torchvision shim — some versions don't expose functional_tensor
    if "torchvision.transforms.functional_tensor" not in sys.modules:
        import torchvision.transforms.functional as _F
        _ft = types.ModuleType("torchvision.transforms.functional_tensor")
        _ft.rgb_to_grayscale = _F.rgb_to_grayscale
        sys.modules["torchvision.transforms.functional_tensor"] = _ft

    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet

    device   = "cuda" if torch.cuda.is_available() else "cpu"
    use_half = device == "cuda"   # float16 only works on GPU
    logging.info(f"Real-ESRGAN device: {device}")

    model_4x = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                       num_block=23, num_grow_ch=32, scale=4)
    upsampler_4x = RealESRGANer(
        scale=4, model_path=WEIGHTS_4X, model=model_4x,
        half=use_half, tile=512, tile_pad=10,
        device=torch.device(device),
    )

    model_2x = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                       num_block=23, num_grow_ch=32, scale=2)
    upsampler_2x = RealESRGANer(
        scale=2, model_path=WEIGHTS_2X, model=model_2x,
        half=use_half, tile=512, tile_pad=10,
        device=torch.device(device),
    )

    return upsampler_4x, upsampler_2x


def upscale_image(image_path: str, longest_side: int) -> np.ndarray:
    """
    Upscales image using Real-ESRGAN until longest side >= UPSCALE_THRESHOLD.
    Uses 4x or 2x passes in a loop (same smart-step logic as Rory).
    Returns BGR numpy array.
    """
    img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    # Drop alpha channel (BGRA → BGR)
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    scale_needed = UPSCALE_THRESHOLD / longest_side
    logging.info(f"Upscaling {os.path.basename(image_path)} — need {scale_needed:.2f}x")

    upsampler_4x, upsampler_2x = _load_realesrgan()

    current_scale = 1.0
    upscaled = img

    while True:
        remaining = scale_needed / current_scale
        if remaining >= 4:
            upscaled, _ = upsampler_4x.enhance(upscaled, outscale=4)
            current_scale *= 4
            logging.info(f"  4x pass done — cumulative: {current_scale:.0f}x")
        elif remaining >= 2:
            upscaled, _ = upsampler_2x.enhance(upscaled, outscale=2)
            current_scale *= 2
            logging.info(f"  2x pass done — cumulative: {current_scale:.0f}x")
        else:
            break

    logging.info(f"Upscale complete — {current_scale:.0f}x total")
    return upscaled


def load_as_numpy(image_path: str) -> np.ndarray:
    """
    Loads image as BGR numpy array without upscaling.
    """
    img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


# ── 4. Center-crop resize ─────────────────────────────────────────────────────

def fit_and_pad(img_array: np.ndarray, target_w: int, target_h: int) -> Image.Image:
    """
    Resizes image to exactly (target_w, target_h). No cropping, no padding, no blur.
    Returns a PIL Image in RGB mode.
    """
    resized = cv2.resize(img_array, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
    result = resized[:, :, ::-1]  # BGR → RGB
    return Image.fromarray(result)


# ── 5. Export 5 print files ───────────────────────────────────────────────────

def export_print_files(img_array: np.ndarray, output_dir: str) -> list[str]:
    """
    Takes a BGR numpy array and writes 5 JPG files into output_dir,
    one per format defined in PRINT_FORMATS.
    Each file: JPEG quality=92, 300 DPI metadata, sRGB.
    Returns list of written file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    written = []

    for stem, target_w, target_h in PRINT_FORMATS:
        pil_image = fit_and_pad(img_array, target_w, target_h)

        # Ensure RGB (handles palette or grayscale inputs)
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        out_path = os.path.join(output_dir, f"{stem}.jpg")
        pil_image.save(
            out_path,
            format="JPEG",
            quality=JPEG_QUALITY,
            dpi=(DPI, DPI),
            icc_profile=_srgb_icc_profile(),
        )
        logging.info(f"  Saved {stem}.jpg — {target_w}x{target_h}px")
        written.append(out_path)

    return written


def _srgb_icc_profile() -> bytes | None:
    """
    Returns the sRGB ICC profile bytes so Pillow embeds it in every JPEG.
    Falls back to None (no profile embedded) if ImageCms is unavailable.
    """
    try:
        from PIL import ImageCms
        srgb = ImageCms.createProfile("sRGB")
        return ImageCms.ImageCmsProfile(srgb).tobytes()
    except Exception:
        return None


# ── 6. Process one set ────────────────────────────────────────────────────────

def process_set(set_folder: str, output_base: str) -> dict:
    """
    Full pipeline for one set folder:
      - Finds all images
      - For each image: detect → maybe upscale → center-crop resize → export 5 files
      - Saves to output_base/<set_name>/print_files/Print_N/

    Returns summary dict: {total, success, failed}
    """
    set_name = os.path.basename(set_folder)
    images   = get_images_in_set(set_folder)

    if not images:
        logging.warning(f"[{set_name}] No images found — skipping")
        return {"total": 0, "success": 0, "failed": 0}

    logging.info(f"[{set_name}] Found {len(images)} image(s)")

    success = 0
    failed  = 0

    for idx, image_path in enumerate(images, start=1):
        print_label = f"Print_{idx}"
        out_dir     = os.path.join(output_base, set_name, "print_files", print_label)
        img_name    = os.path.basename(image_path)

        try:
            should_upscale, longest = needs_upscale(image_path)

            if should_upscale:
                logging.info(f"[{set_name}/{print_label}] {img_name} — longest side {longest}px → upscaling")
                img_array = upscale_image(image_path, longest)
            else:
                logging.info(f"[{set_name}/{print_label}] {img_name} — longest side {longest}px → no upscale needed")
                img_array = load_as_numpy(image_path)

            export_print_files(img_array, out_dir)
            success += 1

        except Exception as e:
            logging.error(f"[{set_name}/{print_label}] FAILED — {img_name}: {e}")
            failed += 1

    return {"total": len(images), "success": success, "failed": failed}
