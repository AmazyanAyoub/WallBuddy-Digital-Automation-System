"""
Full pipeline test on the 'single' set only.
Run: python test_pipeline.py
Output lands in OUTPUT/single/
"""
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import OUTPUT_DIR
from utils.id_counter import get_and_increment
from modules.image_processor  import process_set, get_images_in_set
from modules.mockup_generator  import generate_mockups
from modules.zip_creator       import create_zip
from modules.drive_uploader    import upload_zip
from modules.csv_writer        import append_row

SET_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "INPUT", "single")


def main():
    set_name    = os.path.basename(SET_FOLDER)
    atca_id     = get_and_increment()
    atca_name   = f"ATCA_{atca_id:04d}"
    atca_folder = os.path.join(OUTPUT_DIR, atca_name)

    print(f"\n{'='*55}")
    print(f"  Testing full pipeline on: {set_name} → {atca_name}")
    print(f"{'='*55}\n")

    # ── 1. Image processing ───────────────────────────────────
    print("Step 1/6 — Image processing")
    proc   = process_set(SET_FOLDER, OUTPUT_DIR, atca_id)
    images = get_images_in_set(SET_FOLDER)
    print(f"  {proc['success']} ok / {proc['failed']} failed\n")
    if proc["success"] == 0:
        print("  ERROR: No images processed — stopping.")
        return

    # ── 2. Mockup generation ──────────────────────────────────
    print("Step 2/6 — Mockup generation")
    try:
        mockup_paths = generate_mockups(SET_FOLDER, images, OUTPUT_DIR, atca_id)
        print(f"  {len(mockup_paths)} mockup(s) generated\n")
    except Exception as e:
        print(f"  WARNING: Mockup generation failed (non-fatal): {e}\n")

    # ── 3. ZIP creation ───────────────────────────────────────
    print("Step 3/6 — ZIP creation")
    zip_path = create_zip(atca_folder, atca_id, len(images))
    print(f"  ZIP: {zip_path}\n")

    # # ── 4. Google Drive upload ────────────────────────────────
    # print("Step 4/6 — Google Drive upload")
    # drive_link = upload_zip(zip_path)
    # print(f"  Link: {drive_link}\n")

    # ── 5. Content generation ─────────────────────────────────
    # print("Step 5/6 — Content generation")
    # content = generate_content(set_name, len(images))
    # print(f"  Title ({len(content['title'])} chars): {content['title']}")
    # print(f"  Tags: {', '.join(content['tags'])}\n")

    # # ── 6. CSV row ────────────────────────────────────────────
    # print("Step 6/6 — Writing CSV row")
    # append_row(
    #     set_name    = set_name,
    #     title       = content["title"],
    #     description = content["description"],
    #     tags        = content["tags"],
    #     drive_link  = drive_link,
    # )
    # csv_path = os.path.join(OUTPUT_DIR, "output.csv")
    # print(f"  Written to: {csv_path}\n")

    # print(f"{'='*55}")
    # print(f"  Pipeline complete for: {set_name}")
    # print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
