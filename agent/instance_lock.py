
from filelock import FileLock


class InstanceLock:
    """A thin, non-blocking wrapper around ``filelock.FileLock``."""

    def __init__(self, path):
        self.path = path
        self._lock = FileLock(path)

    def acquire(self):
        """Try to acquire the lock. Returns True on success, False when
        another instance already holds it."""
        try:
            self._lock.acquire(timeout=0)  # non-blocking
            return True
        except TimeoutError:
            return False

    def release(self):
        if self._lock.is_locked:
            self._lock.release()

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("Another instance is already running.")
        return self

    def __exit__(self, *exc):
        self.release()
        return False
