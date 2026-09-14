from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

@dataclass
class SessionResult:
    user_id: str
    device_id: str
    state_id: str
    source: str
    application: str | None
    start_time: datetime
    end_time: datetime | None
    duration_seconds: float

class Sessionizer:

    def sessionize(self, events):
        if not events:
            return []

        grouped = self._group_events(events)

        sessions = []

        for (user_id, device_id, state_id), state_events in grouped.items():

            state_events.sort(
                key=lambda event: (
                    event.timestamp
                )
            )

            result = self._build_session(
                user_id,
                device_id,
                state_id,
                state_events,
            )

            if result:
                sessions.append(result)

        return sessions

    def _group_events(self, events):
        grouped = defaultdict(list)

        for event in events:
            grouped[
                (event.user_id, event.device_id, event.state_id)
            ].append(event)

        return grouped

    def _build_session(self, user_id, device_id, state_id, events):
        first = events[0]

        start_time = first.timestamp
        end_time = None

        for event in events:
            if event.event_type == "STATE_END":
                end_time = event.timestamp
                break

        last_timestamp = (
            end_time
            if end_time
            else events[-1].timestamp
        )

        duration = (
            last_timestamp - start_time
        ).total_seconds()

        return SessionResult(
            user_id=user_id,
            device_id=device_id,
            state_id=state_id,
            source=first.source,
            application=first.application,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=max(0, duration),
        )
