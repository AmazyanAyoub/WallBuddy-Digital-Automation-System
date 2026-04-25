import os, json
import threading

_lock = threading.Lock()
COVER_COUNT   = {"single": 9, "set_3": 9, "set_4": 9, "set_6": 9}
COUNTER_PATH  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cover_index.json")


def get_and_increment(job_type: str) -> int:
    """
    Thread-safe: reads current cover index (1-9), increments it (cycles back to 1),
    saves, and returns the index to use for this image.
    """
    with _lock:
        loaded = False
        if os.path.exists(COUNTER_PATH):
            try:
                with open(COUNTER_PATH, "r") as f:
                    data = json.load(f)
                current = data[job_type]
                loaded = True
            except Exception:
                pass
        if not loaded:
            current = 1
            data = {k: 1 for k in COVER_COUNT}
        next_index = (current % COVER_COUNT[job_type]) + 1
        with open(COUNTER_PATH, "w") as f:
            json.dump({**data, job_type: next_index}, f)
    return current
