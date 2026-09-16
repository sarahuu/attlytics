import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

from agent import config

logger = logging.getLogger(__name__)

# Local setting key holding the user's sync on/off choice.
SYNC_ENABLED_SETTING = "sync_enabled"

_ENDPOINT_PATH = f"{config.API_V1_PREFIX}/heartbeats"


def retry_delay_seconds(consecutive_failures):
    """Backoff for the n-th consecutive failure: 60, 120, 240, then 300s."""
    delays = config.SYNC_RETRY_DELAYS_SECONDS
    index = min(max(consecutive_failures, 1), len(delays)) - 1
    return delays[index]


class SyncWorker(threading.Thread):
    """Uploads PENDING events in timestamp order, in batches of up to N.

    Lifecycle:
        start()            -> begins the loop
        stop()             -> wakes and joins the thread, so shutdown is prompt
        set_enabled(False) -> pauses uploads without stopping the thread
    """

    def __init__(
        self,
        storage,
        stop_event,
        api_base_url=None,
        api_key_loader=None,
        batch_size=None,
        poll_interval=None,
        poster=None,
    ):
        super().__init__(name="sync-worker", daemon=True)
        self._storage = storage
        self._stop_event = stop_event
        base_url = api_base_url if api_base_url is not None else config.API_BASE_URL
        self._api_base_url = base_url.rstrip("/")
        self._api_key_loader = api_key_loader
        self.batch_size = batch_size or config.SYNC_BATCH_SIZE
        self.poll_interval = poll_interval or config.SYNC_POLL_INTERVAL_SECONDS
        # Injectable so tests never touch the network.
        self._poster = poster or self._http_post_batch

        # Woken by enable/disable and stop; never a bare time.sleep().
        self._wake = threading.Event()
        # Set == synchronization enabled.
        self._enabled = threading.Event()
        self._stopping = False
        self._consecutive_failures = 0

        default = "1" if config.SYNC_ENABLED_DEFAULT else "0"
        if self._storage.get_setting(SYNC_ENABLED_SETTING, default) == "1":
            self._enabled.set()

    # ---- Public control ---------------------------------------------------

    def is_enabled(self):
        return self._enabled.is_set()

    def set_enabled(self, enabled):
        """Turn synchronization on/off. Persisted, so it survives restarts.

        Also wakes the worker immediately, so re-enabling does not have to
        wait for the next scheduled attempt.
        """
        enabled = bool(enabled)
        self._storage.set_setting(SYNC_ENABLED_SETTING, "1" if enabled else "0")
        if enabled:
            self._enabled.set()
        else:
            self._enabled.clear()
        self._wake.set()

    def stop(self, timeout=5.0):
        """Wake the worker and wait for it to finish."""
        self._stopping = True
        self._wake.set()
        if self.is_alive():
            self.join(timeout)

    # ---- Loop -------------------------------------------------------------

    def run(self):
        logger.info("Sync worker started (enabled=%s)", self.is_enabled())
        while not self._stopping and not self._stop_event.is_set():
            self._wait(self._run_once())
        logger.info("Sync worker stopped")

    def _run_once(self):
        """One scheduling pass. Returns the seconds to wait before the next
        pass (None means: wait for a wake-up). Never blocks.
        """
        if not self._enabled.is_set():
            return None

        try:
            pending = self._storage.get_pending_events(self.batch_size)
        except Exception:  # noqa: BLE001 - never kill the worker on a DB hiccup
            logger.exception("Could not read pending events")
            return self.poll_interval

        if not pending:
            return self.poll_interval

        event_ids = [event["id"] for event in pending]
        success, error = self._attempt(pending)

        if success:
            self._consecutive_failures = 0
            self._storage.mark_synced(event_ids)
            logger.info("Synced %d events", len(event_ids))
            return 0.0  # drain the backlog straight away

        self._consecutive_failures += 1
        delay = retry_delay_seconds(self._consecutive_failures)
        self._storage.record_sync_failure(
            event_ids,
            error=error,
            next_retry_at=(datetime.now(UTC) + timedelta(seconds=delay)).isoformat(),
        )
        logger.warning(
            "Sync failed (%s); retrying in %.0fs (attempt %d)",
            error,
            delay,
            self._consecutive_failures,
        )
        return delay

    # ---- Internals --------------------------------------------------------

    def _attempt(self, events):
        """One upload attempt. Returns (success, error_message).

        Any failure - no connection, DNS failure, timeout, refused connection,
        server error or 5xx - is a temporary failure: the events stay PENDING
        and are retried on the backoff schedule.
        """
        if not self._api_base_url:
            return False, "API_BASE_URL is not configured"

        api_key = self._api_key_loader() if self._api_key_loader else None
        if not api_key:
            return False, "Device is not connected (no API key)"

        try:
            self._poster([self._to_payload(event) for event in events], api_key)
            return True, None
        except urllib.error.HTTPError as exc:
            return False, f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            return False, f"Network error: {exc.reason}"
        except Exception as exc:  # noqa: BLE001 - treat anything else as temporary
            return False, str(exc)

    @staticmethod
    def _to_payload(event):
        """Map a local row to the API's event schema."""
        metadata = json.loads(event["metadata"]) if event.get("metadata") else {}
        return {
            "local_id": event["id"],
            "state_id": event["state_id"],
            "source": event["source"],
            "application": event["application"],
            "event_type": event["event_type"],
            "timestamp": event["timestamp"],
            "duration_seconds": event.get("duration_seconds"),
            "process_id": metadata.get("process_id"),
            "window_title": metadata.get("window_title"),
        }

    def _http_post_batch(self, payload, api_key):
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._api_base_url + _ENDPOINT_PATH,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                # The device API key authenticates this machine.
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _wait(self, seconds):
        """Wait for a wake-up/stop, or the given timeout. Never a bare sleep."""
        self._wake.wait(timeout=seconds)
        self._wake.clear()
