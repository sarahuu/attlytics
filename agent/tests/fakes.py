from datetime import datetime, timedelta, timezone


class FakeObserver:
    """Returns a scripted sequence of observations.

    Repeats the last observation after the script is exhausted so polling a
    stable state behaves deterministically.
    """

    def __init__(self, observations):
        self.observations = list(observations)
        self.calls = 0

    def __call__(self):
        if not self.observations:
            return None
        index = min(self.calls, len(self.observations) - 1)
        self.calls += 1
        return self.observations[index]


class FakeClock:
    """Deterministic time provider for tests.

    ``now()`` returns an aware UTC datetime for event timestamps and
    ``monotonic()`` returns a float used for observation-interval math.
    ``advance()`` moves both forward together.
    """

    def __init__(self, start_time=None, start_monotonic=0.0):
        self._now = start_time or datetime(
            2026, 8, 26, 10, 0, 0, tzinfo=timezone.utc
        )
        self._monotonic = start_monotonic

    def now(self):
        return self._now

    def monotonic(self):
        return self._monotonic

    def advance(self, seconds):
        self._now += timedelta(seconds=seconds)
        self._monotonic += seconds
