import asyncio
from logging import getLogger
from typing import Awaitable, Callable, Sequence, Type, Union

logger = getLogger(__name__)


def retry[T, **P](
    max_delay: int, retry_on: Union[Type[Exception], Sequence[Type[Exception]]]
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    def wrapper(operation: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        async def execute(*args: P.args, **kwargs: P.kwargs) -> T:
            delay = 0

            while True:
                await asyncio.sleep(delay)

                try:
                    return await operation(*args, **kwargs)
                except retry_on as exc:  # pyright: ignore [reportGeneralTypeIssues]
                    if delay == max_delay:
                        logger.exception(
                            "Execution of operation %s failed and maximum retry period %s minutes closed."
                            + "\n args: %s\n kwargs: %s",
                            operation.__name__,
                            max_delay / 60,
                            args,
                            kwargs,
                        )
                        raise RuntimeError from exc

                    delay = min(30 if delay == 0 else delay * 2, max_delay)

                    logger.warning(
                        "Execution of operation %s failed and will be retried in %s minutes.\n args: %s\n kwargs: %s",
                        operation.__name__,
                        delay / 60,
                        args,
                        kwargs,
                    )

        return execute

    return wrapper
