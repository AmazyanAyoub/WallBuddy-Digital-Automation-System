import os
import zipfile
import logging

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import OUTPUT_DIR


def create_zip(atca_folder: str, atca_id: int, image_count: int) -> str:
    """
    Zips all print files for a set into ATCA_000{id}.zip.

    Single image:    zips JPGs directly from atca_folder/
    Multiple images: zips JPGs from atca_folder/ATCA_000{id}_N/ subfolders

    Returns the path to the created ZIP file.
    """
    atca_name = f"ATCA_{atca_id:04d}"
    zip_path  = os.path.join(atca_folder, f"{atca_name}.zip")
    is_single = image_count == 1

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if is_single:
            for entry in sorted(os.scandir(atca_folder), key=lambda e: e.name):
                if entry.is_file() and entry.name.endswith(".jpg"):
                    zf.write(entry.path, entry.name)
                    logging.info(f"[{atca_name}] Zipped: {entry.name}")
        else:
            for idx in range(1, image_count + 1):
                img_label  = f"{atca_name}_{idx}"
                img_folder = os.path.join(atca_folder, img_label)
                if not os.path.isdir(img_folder):
                    logging.warning(f"[{atca_name}] Subfolder not found: {img_folder} — skipping")
                    continue
                for entry in sorted(os.scandir(img_folder), key=lambda e: e.name):
                    if entry.is_file() and entry.name.endswith(".jpg"):
                        arcname = f"{img_label}/{entry.name}"
                        zf.write(entry.path, arcname)
                        logging.info(f"[{atca_name}] Zipped: {arcname}")

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    logging.info(f"[{atca_name}] ZIP created: {zip_path} ({size_mb:.1f} MB)")
    return zip_path
