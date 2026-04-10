import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import INPUT_DIR, OUTPUT_DIR, LOG_DIR
from utils.logger import setup_logging
from modules.image_processor  import process_set, get_images_in_set
from modules.mockup_generator  import generate_mockups
from modules.zip_creator       import create_zip
from modules.drive_uploader    import upload_zip
from modules.content_generator import generate_content
from modules.csv_writer        import append_row


def scan_sets(input_dir: str) -> list[str]:
    """Returns sorted list of set folder paths found in input_dir."""
    sets = []
    for entry in sorted(os.scandir(input_dir), key=lambda e: e.name.lower()):
        if entry.is_dir():
            sets.append(entry.path)
    return sets


def run_set(set_folder: str) -> tuple[str, dict]:
    """
    Full pipeline for one set:
      1. Image processing   → print_files/Print_N/ (5 JPGs each)
      2. Mockup generation  → mockups/ (5 mockup JPGs)
      3. ZIP creation       → set_name.zip
      4. Google Drive upload→ public URL
      5. Content generation → title, description, tags via Gemini
      6. CSV row            → OUTPUT/output.csv
    Each step is isolated — a failure logs and skips remaining steps for that set.
    """
    set_name    = os.path.basename(set_folder)
    result      = {"success": False, "error": None}

    # ── 1. Image processing ───────────────────────────────────────────────────
    try:
        logging.info(f"[{set_name}] Step 1/6 — Image processing")
        proc   = process_set(set_folder, OUTPUT_DIR)
        images = get_images_in_set(set_folder)
        logging.info(f"[{set_name}] Images: {proc['success']} ok / {proc['failed']} failed")
        if proc["success"] == 0:
            raise RuntimeError("No images processed successfully")
    except Exception as e:
        logging.error(f"[{set_name}] Image processing failed: {e}")
        result["error"] = str(e)
        return set_name, result

    # ── 2. Mockup generation ──────────────────────────────────────────────────
    try:
        logging.info(f"[{set_name}] Step 2/6 — Mockup generation")
        mockup_paths = generate_mockups(set_folder, images, OUTPUT_DIR)
        logging.info(f"[{set_name}] {len(mockup_paths)} mockup(s) generated")
    except Exception as e:
        logging.error(f"[{set_name}] Mockup generation failed: {e}")
        # Non-fatal — continue pipeline without mockups

    # ── 3. ZIP creation ───────────────────────────────────────────────────────
    try:
        logging.info(f"[{set_name}] Step 3/6 — ZIP creation")
        zip_path = create_zip(set_folder, OUTPUT_DIR)
    except Exception as e:
        logging.error(f"[{set_name}] ZIP creation failed: {e}")
        result["error"] = str(e)
        return set_name, result

    # ── 4. Google Drive upload ────────────────────────────────────────────────
    try:
        logging.info(f"[{set_name}] Step 4/6 — Google Drive upload")
        drive_link = upload_zip(zip_path)
    except Exception as e:
        logging.error(f"[{set_name}] Drive upload failed: {e}")
        result["error"] = str(e)
        return set_name, result

    # ── 5. Content generation ─────────────────────────────────────────────────
    try:
        logging.info(f"[{set_name}] Step 5/6 — Content generation")
        content = generate_content(set_name, len(images))
    except Exception as e:
        logging.error(f"[{set_name}] Content generation failed: {e}")
        result["error"] = str(e)
        return set_name, result

    # ── 6. CSV row ────────────────────────────────────────────────────────────
    try:
        logging.info(f"[{set_name}] Step 6/6 — Writing CSV row")
        append_row(
            set_name   = set_name,
            title      = content["title"],
            description= content["description"],
            tags       = content["tags"],
            drive_link = drive_link,
        )
    except Exception as e:
        logging.error(f"[{set_name}] CSV write failed: {e}")
        result["error"] = str(e)
        return set_name, result

    result["success"] = True
    logging.info(f"[{set_name}] Pipeline complete")
    return set_name, result


def main():
    setup_logging(LOG_DIR)

    sets = scan_sets(INPUT_DIR)
    if not sets:
        logging.warning(f"No set folders found in {INPUT_DIR} — nothing to do.")
        return

    logging.info(f"Found {len(sets)} set(s) to process")

    total   = len(sets)
    success = 0
    failed  = 0

    max_workers = min(4, total)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_set, s): s for s in sets}
        for future in as_completed(futures):
            set_name, result = future.result()
            if result["success"]:
                success += 1
            else:
                failed += 1
                logging.error(f"[{set_name}] Failed at: {result['error']}")

    logging.info(
        f"\n{'='*50}\n"
        f"  Sets : {success} complete / {failed} failed / {total} total\n"
        f"  CSV  : {os.path.join(OUTPUT_DIR, 'output.csv')}\n"
        f"{'='*50}"
    )


if __name__ == "__main__":
    main()
