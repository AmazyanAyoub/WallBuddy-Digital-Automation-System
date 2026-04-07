import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import INPUT_DIR, OUTPUT_DIR, LOG_DIR
from utils.logger import setup_logging
from modules.image_processor import process_set


def scan_sets(input_dir: str) -> list[str]:
    """Returns sorted list of set folder paths found in input_dir."""
    sets = []
    for entry in sorted(os.scandir(input_dir), key=lambda e: e.name.lower()):
        if entry.is_dir():
            sets.append(entry.path)
    return sets


def run_set(set_folder: str) -> tuple[str, dict]:
    """Wrapper so ThreadPoolExecutor can call process_set and return the set name with result."""
    set_name = os.path.basename(set_folder)
    try:
        result = process_set(set_folder, OUTPUT_DIR)
    except Exception as e:
        logging.error(f"[{set_name}] Unhandled error: {e}")
        result = {"total": 0, "success": 0, "failed": 1}
    return set_name, result


def main():
    setup_logging(LOG_DIR)

    sets = scan_sets(INPUT_DIR)
    if not sets:
        logging.warning(f"No set folders found in {INPUT_DIR} — nothing to do.")
        return

    logging.info(f"Found {len(sets)} set(s) to process")

    total_sets    = len(sets)
    sets_ok       = 0
    sets_failed   = 0
    images_ok     = 0
    images_failed = 0

    # Process sets in parallel (safe: each set writes to its own output folder)
    max_workers = min(4, total_sets)   # cap at 4 — Real-ESRGAN is GPU/CPU heavy
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_set, s): s for s in sets}
        for future in as_completed(futures):
            set_name, result = future.result()
            images_ok     += result["success"]
            images_failed += result["failed"]
            if result["failed"] == 0 and result["total"] > 0:
                sets_ok += 1
            elif result["total"] == 0:
                sets_failed += 1
            else:
                sets_failed += 1

    logging.info(
        f"\n{'='*50}\n"
        f"  Sets    : {sets_ok} ok / {sets_failed} with errors / {total_sets} total\n"
        f"  Images  : {images_ok} ok / {images_failed} failed\n"
        f"{'='*50}"
    )


if __name__ == "__main__":
    main()
