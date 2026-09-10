import logging
import platform
import threading
import time
from datetime import datetime, timezone

from agent.collectors.windows import WindowsCollector
from agent.config import (
    DB_PATH,
    HEARTBEAT_INTERVAL_SECONDS,
    IDENTITY_PATH,
    IDLE_THRESHOLD_SECONDS,
    POLL_INTERVAL_SECONDS,
)
from agent.identity import load_or_create_identity
from agent.instance_lock import InstanceLock
from agent.storage.database import ActivityDatabase
from agent.tracking.activity_tracker import ActivityTracker

logger = logging.getLogger(__name__)


class SystemClock:
    """Real time provider used in production."""

    def now(self):
        return datetime.now(timezone.utc)

    def monotonic(self):
        return time.monotonic()


def create_collector():
    system = platform.system()

    if system == "Windows":
        return WindowsCollector()

    raise RuntimeError(
        f"Unsupported operating system: {system}"
    )


def run(stop_event=None):
    """Run the agent loop until ``stop_event`` is set (or Ctrl+C in a
    console). Returns after a clean shutdown."""
    if stop_event is None:
        stop_event = threading.Event()

    # Take the single-instance lock before touching identity/secrets so two
    # simultaneous first runs cannot race on creating identity.json.
    lock = InstanceLock(DB_PATH.parent / f"{DB_PATH.name}.lock")
    if not lock.acquire():
        logger.warning(
            "Another agent instance is already running (lock: %s). Exiting.",
            lock.path,
        )
        return

    try:
        load_or_create_identity(IDENTITY_PATH)

        collector = create_collector()
        storage = ActivityDatabase(DB_PATH)
        storage.initialize()

        tracker = ActivityTracker(
            observer=collector.get_active_application,
            storage=storage,
            clock=SystemClock(),
            heartbeat_interval=HEARTBEAT_INTERVAL_SECONDS,
            idle_threshold=IDLE_THRESHOLD_SECONDS,
        )

        try:
            while not stop_event.is_set():
                tracker.observe()
                time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            pass
        finally:
            storage.close()
    finally:
        lock.release()


def main():
    """Console entry point: runs until Ctrl+C."""
    run()


if __name__ == "__main__":
    main()