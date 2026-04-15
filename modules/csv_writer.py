import os
import csv
import logging
import threading

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import OUTPUT_DIR

CSV_PATH    = os.path.join(OUTPUT_DIR, "output.csv")
CSV_COLUMNS = ["ATCA_ID", "Drive_Link"]

_csv_lock = threading.Lock()


def _ensure_header(path: str) -> None:
    if not os.path.isfile(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=CSV_COLUMNS).writeheader()


def append_row(atca_name: str, drive_link: str) -> None:
    """Appends one row (ATCA_ID, Drive_Link) to OUTPUT/output.csv. Thread-safe."""
    with _csv_lock:
        _ensure_header(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=CSV_COLUMNS).writerow({
                "ATCA_ID"   : atca_name,
                "Drive_Link": drive_link,
            })
    logging.info(f"[{atca_name}] CSV row written → {CSV_PATH}")
