import logging
import sys
from logging.handlers import RotatingFileHandler

from agent import config

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    handlers: list[logging.Handler] = []

    try:
        config.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                config.LOG_PATH,
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
        )
    except OSError:
        pass  # no writable location -> fall back to the console only

    # Mirror to the console for source runs; the frozen exe has no console.
    if not getattr(sys, "frozen", False):
        handlers.append(logging.StreamHandler())

    if not handlers:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )


def main():
    _setup_logging()
    logger.info("attlytics-agent starting; data folder: %s", config.LOG_PATH.parent)

    if "--agent" in sys.argv:
        from agent.main import run as run_agent

        run_agent()
    else:
        from agent.tray import run_app

        run_app()


if __name__ == "__main__":
    main()
