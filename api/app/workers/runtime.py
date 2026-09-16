import asyncio
import selectors
import sys
from collections.abc import Coroutine
from typing import Any, TypeVar

from celery.signals import worker_process_shutdown

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None


def _new_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.new_event_loop()


def get_loop() -> asyncio.AbstractEventLoop:
    global _loop

    if _loop is None or _loop.is_closed():
        _loop = _new_loop()

    return _loop


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    return get_loop().run_until_complete(coro)


@worker_process_shutdown.connect
def _dispose(**_kwargs: Any) -> None:
    global _loop

    if _loop is None:
        return

    from app.db.session import engine

    _loop.run_until_complete(engine.dispose())
    _loop.close()
    _loop = None
