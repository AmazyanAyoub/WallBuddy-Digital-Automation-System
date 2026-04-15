import os
import threading

_lock = threading.Lock()
COVER_COUNT   = 9
COUNTER_PATH  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cover_index.txt")


def get_and_increment() -> int:
    """
    Thread-safe: reads current cover index (1-9), increments it (cycles back to 1),
    saves, and returns the index to use for this image.
    """
    with _lock:
        if os.path.exists(COUNTER_PATH):
            with open(COUNTER_PATH, "r") as f:
                current = int(f.read().strip())
        else:
            current = 1
        next_index = (current % COVER_COUNT) + 1
        with open(COUNTER_PATH, "w") as f:
            f.write(str(next_index))
    return current
