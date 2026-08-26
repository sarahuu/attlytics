import uuid

from agent.config import (
    HEARTBEAT_INTERVAL_SECONDS,
    IDLE_THRESHOLD_SECONDS,
)

# Event types recorded by the tracker.
STATE_START = "STATE_START"
HEARTBEAT = "HEARTBEAT"
STATE_END = "STATE_END"

# Local synchronization states (reserved for a future sync worker).
PENDING = "PENDING"
SYNCED = "SYNCED"
FAILED = "FAILED"

# Application identifier used for the idle state.
IDLE = "idle"

SOURCE = "os"


class ActivityTracker:
    """
    Decides what events to record from an observation of the active
    application.

    Responsibilities:
        - Track one continuous state (application, state_id, last event time)
          in memory.
        - Emit STATE_START on the first observation of a state.
        - Emit HEARTBEAT every ``heartbeat_interval`` seconds while the same
          state stays active.
        - Emit STATE_END (old state_id) followed by STATE_START (new state_id)
          when the state changes.
        - Track idle as its own state (application == IDLE) once the user has
          been without input for ``idle_threshold`` seconds.

    The tracker only records observations; it never derives sessions.
    Session derivation is a server-side concern.
    """

    def __init__(
        self,
        observer,
        storage,
        clock,
        heartbeat_interval=HEARTBEAT_INTERVAL_SECONDS,
        idle_threshold=IDLE_THRESHOLD_SECONDS,
        source=SOURCE,
    ):
        self._observer = observer
        self._storage = storage
        self._clock = clock
        self.heartbeat_interval = heartbeat_interval
        self.idle_threshold = idle_threshold
        self.source = source

        # One continuous observed state, kept in memory.
        #   application     normalized application identifier
        #   state_id        shared by every event of this state
        #   last_event_at   monotonic time of the last recorded event
        self.current_state = None

        # Most recent raw observation; used for STATE_END metadata.
        self._last_observation = None

    def observe(self):
        """Poll the observer, decide which events to record, persist them, and
        return the list of recorded events (empty when nothing changed)."""
        observation = self._observer()
        if observation is None:
            # No observation at all. Record nothing and keep the current
            # state in memory.
            return []

        application = self._normalize_application(observation)
        idle_seconds = observation.get("idle_seconds")
        is_idle = (
            idle_seconds is not None
            and idle_seconds >= self.idle_threshold
        )

        # Not idle but no foreground window to observe: record nothing.
        if not is_idle and application is None:
            return []

        # Idle is its own state. While idle the foreground app is ignored,
        # so app switches during idle periods are not recorded.
        if is_idle:
            active_app = IDLE
            active_observation = None
        else:
            active_app = application
            active_observation = observation

        now_monotonic = self._clock.monotonic()
        previous_observation = self._last_observation
        self._last_observation = observation

        # First observation of this tracker run: start a new state.
        if self.current_state is None:
            event = self._build_event(
                STATE_START,
                state_id=str(uuid.uuid4()),
                application=active_app,
                duration_seconds=idle_seconds if is_idle else 0.0,
                observation=active_observation,
            )
            self._persist(event)
            self.current_state = {
                "application": active_app,
                "state_id": event["state_id"],
                "last_event_at": now_monotonic,
            }
            return [event]

        elapsed = now_monotonic - self.current_state["last_event_at"]

        # The state changed: end the old state, start a new one.
        if self.current_state["application"] != active_app:
            if is_idle:
                # Transitioning to idle: split the observation window into the
                # portion that was still active (elapsed - idle_seconds) and
                # the portion that was idle (idle_seconds) so the interval is
                # not double-counted.
                end_duration = max(0.0, elapsed - idle_seconds)
                start_duration = idle_seconds
            else:
                end_duration = elapsed
                start_duration = 0.0

            end_event = self._build_event(
                STATE_END,
                state_id=self.current_state["state_id"],
                application=self.current_state["application"],
                duration_seconds=end_duration,
                observation=previous_observation,
            )
            start_event = self._build_event(
                STATE_START,
                state_id=str(uuid.uuid4()),
                application=active_app,
                duration_seconds=start_duration,
                observation=active_observation,
            )
            self._persist(end_event)
            self._persist(start_event)
            self.current_state = {
                "application": active_app,
                "state_id": start_event["state_id"],
                "last_event_at": now_monotonic,
            }
            return [end_event, start_event]

        # Same state still active: emit a heartbeat once the observation
        # interval has elapsed.
        if elapsed >= self.heartbeat_interval:
            event = self._build_event(
                HEARTBEAT,
                state_id=self.current_state["state_id"],
                application=active_app,
                duration_seconds=elapsed,
                observation=active_observation,
            )
            self._persist(event)
            self.current_state["last_event_at"] = now_monotonic
            return [event]

        return []

    def _normalize_application(self, observation):
        """Return the normalized application identifier from an observation."""
        name = observation.get("process_name")
        return name.lower() if name else None

    def _build_event(self, event_type, state_id, application, duration_seconds, observation):
        """Build an event dict. duration_seconds is the observation interval
        associated with this event. The first STATE_START of an application
        state carries 0.0 because nothing has been observed yet at that
        instant; the idle STATE_START instead carries the observed idle time."""
        return {
            "id": str(uuid.uuid4()),
            "state_id": state_id,
            "source": self.source,
            "application": application,
            "event_type": event_type,
            "timestamp": self._clock.now().isoformat(),
            "duration_seconds": duration_seconds,
            "metadata": {
                "process_id": observation.get("process_id") if observation else None,
                "window_title": observation.get("window_title") if observation else None,
            },
            "sync_status": PENDING,
        }

    def _persist(self, event):
        self._storage.insert_event(event)
