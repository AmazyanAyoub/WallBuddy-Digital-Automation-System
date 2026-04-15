import os
import threading

_lock = threading.Lock()
COUNTER_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "id_counter.txt")


def get_and_increment() -> int:
    """
    Thread-safe: reads current ID, saves next ID, returns current.
    Starts at 1 if no counter file exists yet.
    """
    with _lock:
        if os.path.exists(COUNTER_PATH):
            with open(COUNTER_PATH, "r") as f:
                current = int(f.read().strip())
        else:
            current = 1
        with open(COUNTER_PATH, "w") as f:
            f.write(str(current + 1))
    return current
