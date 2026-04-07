import os
import sys
import logging
from datetime import datetime


def setup_logging(log_dir: str) -> None:
    """
    Configures root logger:
    - File handler  → logs/errors.log  (INFO and above, persists across runs)
    - Stream handler → stdout           (INFO and above, live feedback)
    A failure in one set must never crash the run — callers catch exceptions
    and call logging.error(); this logger just records them.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "errors.log")

    formatter = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Avoid duplicate handlers if setup_logging is called more than once
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    logging.info(f"Logging started — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
