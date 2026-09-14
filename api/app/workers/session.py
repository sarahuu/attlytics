import asyncio
import logging
import selectors

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.heartbeat import Session
from app.repos.sessions import (
    ActivityRepository,
)
from app.services.session import Sessionizer
from app.db.session import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


class SessionizationWorker:

    def __init__(
        self,
        poll_interval: int = 30,
    ):
        self.poll_interval = poll_interval
        self.sessionizer = Sessionizer()
        self.count = 0

    async def process_batch(self):

        async with SessionLocal() as db:

            repository = ActivityRepository(db)

            events = await repository.get_pending_events(
                limit=100
            )

            if not events:
                return False

            sessions = self.sessionizer.sessionize(
                events
            )
            keys = [
                (result.user_id, result.device_id, result.state_id)
                for result in sessions
            ]
            existing_map = await repository.get_existing_sessions(keys)

            for result in sessions:

                existing = existing_map.get((result.user_id, result.device_id, result.state_id))

                if existing:
                    if result.start_time < existing.start_time:
                        existing.start_time = result.start_time

                    if existing.end_time is None:
                        existing.end_time = result.end_time
                    elif result.end_time is not None:
                        existing.end_time = max(existing.end_time, result.end_time)

                    if existing.end_time is not None:
                        existing.duration_seconds = (
                            existing.end_time - existing.start_time
                        ).total_seconds()

                    existing.updated_at = result.end_time or result.start_time

                else:

                    session = Session(
                        user_id=result.user_id,
                        device_id=result.device_id,
                        state_id=result.state_id,
                        source=result.source,
                        application=result.application,
                        start_time=result.start_time,
                        end_time=result.end_time,
                        duration_seconds=(
                            result.duration_seconds
                        ),
                    )

                    await repository.create_session(
                        session
                    )

            await repository.mark_events_sessionized(
                [event.id for event in events]
            )

            await db.commit()

            return True

    async def run(self):

        logger.info(
            "Sessionization worker started"
        )

        while True:

            try:
                processed = await self.process_batch()

                if processed:
                    self.count += 1
                    logger.info(
                        f"Processed batch of events (total: {self.count})"
                    )
                    continue

            except Exception:

                logger.exception(
                    "Sessionization worker failed"
                )

            await asyncio.sleep(
                self.poll_interval
            )

async def main():
    logger.info("Worker STarted")
    worker = SessionizationWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))