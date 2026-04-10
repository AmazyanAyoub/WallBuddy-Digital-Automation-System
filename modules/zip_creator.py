import os
import zipfile
import logging

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import OUTPUT_DIR


def create_zip(set_folder: str, output_base: str) -> str:
    """
    Zips all print files for a set into set_name.zip.

    Reads from:  output_base/set_name/print_files/Print_N/*.jpg
    Writes to:   output_base/set_name/set_name.zip

    Internal ZIP structure:
        Print 1/2x3_ratio_24x36.jpg
        Print 1/3x4_ratio_18x24.jpg
        ...
        Print 2/...

    Returns the path to the created ZIP file.
    """
    set_name      = os.path.basename(set_folder)
    print_files_dir = os.path.join(output_base, set_name, "print_files")
    zip_path      = os.path.join(output_base, set_name, f"{set_name}.zip")

    if not os.path.isdir(print_files_dir):
        raise FileNotFoundError(f"[{set_name}] print_files dir not found: {print_files_dir}")

    # Collect Print_N folders sorted
    print_folders = sorted(
        [e for e in os.scandir(print_files_dir) if e.is_dir() and e.name.startswith("Print_")],
        key=lambda e: int(e.name.split("_")[1])
    )

    if not print_folders:
        raise ValueError(f"[{set_name}] No Print_N folders found in {print_files_dir}")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for folder_entry in print_folders:
            # "Print_1" → "Print 1" inside the ZIP (space, not underscore)
            folder_num   = folder_entry.name.split("_")[1]
            zip_folder   = f"Print {folder_num}"

            for file_entry in sorted(os.scandir(folder_entry.path), key=lambda e: e.name):
                if not file_entry.is_file():
                    continue
                arcname = f"{zip_folder}/{file_entry.name}"
                zf.write(file_entry.path, arcname)
                logging.info(f"[{set_name}] Zipped: {arcname}")

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    logging.info(f"[{set_name}] ZIP created: {zip_path} ({size_mb:.1f} MB)")
    return zip_path
