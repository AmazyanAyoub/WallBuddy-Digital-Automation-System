import os
import csv
import logging
import threading

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import OUTPUT_DIR

CSV_PATH    = os.path.join(OUTPUT_DIR, "output.csv")
CSV_COLUMNS = ["Title", "Description", "Tags", "Drive_Link"]

# Lock so parallel set threads don't corrupt the CSV simultaneously
_csv_lock = threading.Lock()


def _ensure_header(path: str) -> None:
    """Creates the CSV with header row if it doesn't exist yet."""
    if not os.path.isfile(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()


def append_row(set_name: str, title: str, description: str, tags: list[str], drive_link: str) -> None:
    """
    Appends one row to OUTPUT/output.csv.
    Tags list is joined into a single comma-separated string.
    Thread-safe via module-level lock.
    """
    tags_str = ", ".join(tags)
    row = {
        "Title"      : title,
        "Description": description,
        "Tags"       : tags_str,
        "Drive_Link" : drive_link,
    }

    with _csv_lock:
        _ensure_header(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writerow(row)

    logging.info(f"[{set_name}] CSV row written → {CSV_PATH}")
