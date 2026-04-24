import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import INPUT_DIR, OUTPUT_DIR, LOG_DIR, IMAGE_EXTENSIONS
from utils.logger import setup_logging
from utils.id_counter import get_and_increment
from modules.image_processor  import process_set, get_images_in_set
from modules.mockup_generator  import generate_mockups
from modules.zip_creator       import create_zip
from modules.drive_uploader    import upload_zip
from modules.csv_writer        import append_row


def scan_jobs(input_dir: str) -> list[str]:
    """
    Returns a list of jobs to process:
    - 'single' folder → each image inside becomes its own job (image path)
    - 'set_3' folder  → images grouped in batches of 3, each batch is one job (tuple of 3 paths)
    - all other folders → treated as a set (folder path)
    """
    jobs = []
    for entry in sorted(os.scandir(input_dir), key=lambda e: e.name.lower()):
        if not entry.is_dir():
            continue
        if entry.name == "single":
            for img in sorted(os.scandir(entry.path), key=lambda e: e.name.lower()):
                if img.is_file() and os.path.splitext(img.name)[1].lower() in IMAGE_EXTENSIONS:
                    jobs.append(img.path)
        elif entry.name == "set_3":
            images = [
                img.path
                for img in sorted(os.scandir(entry.path), key=lambda e: e.name.lower())
                if img.is_file() and os.path.splitext(img.name)[1].lower() in IMAGE_EXTENSIONS
            ]
            if len(images) == 0:
                logging.warning("[set_3] No images found — skipping")
            elif len(images) % 3 != 0:
                raise ValueError(
                    f"[set_3] Image count must be a multiple of 3, got {len(images)}"
                )
            else:
                logging.info(f"[set_3] {len(images)} images → {len(images) // 3} group(s) of 3")
                for i in range(0, len(images), 3):
                    jobs.append(tuple(images[i:i + 3]))
        
        elif entry.name == "set_4":
            images = [
                img.path
                for img in sorted(os.scandir(entry.path), key=lambda e: e.name.lower())
                if img.is_file() and os.path.splitext(img.name)[1].lower() in IMAGE_EXTENSIONS
            ]
            if len(images) == 0:
                logging.warning("[set_4] No images found — skipping")
            elif len(images) % 4 != 0:
                raise ValueError(
                    f"[set_4] Image count must be a multiple of 4, got {len(images)}"
                )
            else:
                logging.info(f"[set_4] {len(images)} images → {len(images) // 4} group(s) of 4")
                for i in range(0, len(images), 4):
                    jobs.append(tuple(images[i:i + 4]))

        else:
            jobs.append(entry.path)
    return jobs


def _delete_print_files(atca_folder: str, atca_id: int, image_count: int) -> None:
    """Deletes all generated JPG print files after ZIP is created, keeps mockups and ZIP."""
    atca_name = f"ATCA_{atca_id:04d}"
    is_single = image_count == 1

    if is_single:
        for entry in os.scandir(atca_folder):
            if entry.is_file() and entry.name.endswith(".jpg"):
                os.remove(entry.path)
                logging.info(f"[{atca_name}] Deleted: {entry.name}")
    else:
        for idx in range(1, image_count + 1):
            img_folder = os.path.join(atca_folder, f"{atca_name}_{idx}")
            if not os.path.isdir(img_folder):
                continue
            for entry in os.scandir(img_folder):
                if entry.is_file() and entry.name.endswith(".jpg"):
                    os.remove(entry.path)
                    logging.info(f"[{atca_name}] Deleted: {atca_name}_{idx}/{entry.name}")
            # Remove empty subfolder
            if not os.listdir(img_folder):
                os.rmdir(img_folder)

    # Delete temp/ folder (hires sources used for mockups)
    import shutil
    temp_folder = os.path.join(atca_folder, "temp")
    if os.path.isdir(temp_folder):
        shutil.rmtree(temp_folder)
        logging.info(f"[{atca_name}] Deleted temp/ folder")


def run_job(job) -> tuple[str, dict]:
    """
    Full pipeline for one job:
      - job is an image path   → single image (from 'single' folder), job_type='single'
      - job is a tuple of paths → group of 3 images (from 'set_3' folder), job_type='set_3'
      - job is a folder path   → full set, job_type='single'
    Steps: image processing → mockups → ZIP → delete prints → Drive upload → CSV
    """
    if isinstance(job, tuple):
        images     = list(job)
        set_folder = os.path.dirname(images[0])
        job_label  = f"set_3_{os.path.splitext(os.path.basename(images[0]))[0]}"
        job_type   = "set_3"
    elif isinstance(job, tuple):
        images     = list(job)
        set_folder = os.path.dirname(images[0])
        job_label  = f"set_4_{os.path.splitext(os.path.basename(images[0]))[0]}"
        job_type   = "set_4"
    elif os.path.isfile(job):
        images     = [job]
        set_folder = os.path.dirname(job)
        job_label  = os.path.splitext(os.path.basename(job))[0]
        job_type   = "single"
    else:
        set_folder = job
        images     = get_images_in_set(set_folder)
        job_label  = os.path.basename(set_folder)
        job_type   = "single"

    atca_id     = get_and_increment()
    atca_name   = f"ATCA_{atca_id:04d}"
    atca_folder = os.path.join(OUTPUT_DIR, atca_name)
    result      = {"success": False, "error": None}

    # ── 1. Image processing ───────────────────────────────────────────────────
    try:
        logging.info(f"[{job_label}] Step 1/5 — Image processing → {atca_name} (type={job_type})")
        proc = process_set(set_folder, OUTPUT_DIR, atca_id, images=images)
        hires_paths = proc.get("hires_paths", images)
        logging.info(f"[{atca_name}] Images: {proc['success']} ok / {proc['failed']} failed")
        if proc["success"] == 0:
            raise RuntimeError("No images processed successfully")
    except Exception as e:
        logging.error(f"[{atca_name}] Image processing failed: {e}")
        result["error"] = str(e)
        return job_label, result

    # ── 2. Mockup generation ──────────────────────────────────────────────────
    try:
        logging.info(f"[{atca_name}] Step 2/5 — Mockup generation")
        mockup_paths = generate_mockups(set_folder, hires_paths, OUTPUT_DIR, atca_id, job_type=job_type)
        logging.info(f"[{atca_name}] {len(mockup_paths)} mockup(s) generated")
    except Exception as e:
        logging.error(f"[{atca_name}] Mockup generation failed: {e}")

    # ── 3. ZIP + delete prints ────────────────────────────────────────────────
    try:
        logging.info(f"[{atca_name}] Step 3/5 — ZIP creation")
        zip_path = create_zip(atca_folder, atca_id, len(images))
        _delete_print_files(atca_folder, atca_id, len(images))
    except Exception as e:
        logging.error(f"[{atca_name}] ZIP creation failed: {e}")
        result["error"] = str(e)
        return job_label, result

    # ── 4. Google Drive upload ────────────────────────────────────────────────
    try:
        logging.info(f"[{atca_name}] Step 4/5 — Google Drive upload")
        drive_link = upload_zip(zip_path, atca_name)
    except Exception as e:
        logging.error(f"[{atca_name}] Drive upload failed: {e}")
        result["error"] = str(e)
        return job_label, result

    # ── 5. CSV row ────────────────────────────────────────────────────────────
    try:
        logging.info(f"[{atca_name}] Step 5/5 — Writing CSV row")
        append_row(atca_name=atca_name, drive_link=drive_link)
    except Exception as e:
        logging.error(f"[{atca_name}] CSV write failed: {e}")
        result["error"] = str(e)
        return job_label, result

    result["success"] = True
    logging.info(f"[{atca_name}] Pipeline complete")
    return job_label, result


def main():
    setup_logging(LOG_DIR)

    jobs = scan_jobs(INPUT_DIR)
    if not jobs:
        logging.warning(f"No jobs found in {INPUT_DIR} — nothing to do.")
        return

    logging.info(f"Found {len(jobs)} job(s) to process")

    total   = len(jobs)
    success = 0
    failed  = 0

    max_workers = min(4, total)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_job, j): j for j in jobs}
        for future in as_completed(futures):
            job_label, result = future.result()
            if result["success"]:
                success += 1
            else:
                failed += 1
                logging.error(f"[{job_label}] Failed at: {result['error']}")

    logging.info(
        f"\n{'='*50}\n"
        f"  Jobs: {success} complete / {failed} failed / {total} total\n"
        f"  CSV : {os.path.join(OUTPUT_DIR, 'output.csv')}\n"
        f"{'='*50}"
    )


if __name__ == "__main__":
    main()
