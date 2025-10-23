import asyncio
import copy
from logging import Logger, getLogger
from typing import Annotated, Any, Awaitable, Callable, Final, Sequence, Type, Union

from pydantic import Field

_logger: Final[Logger] = getLogger(__name__)


NotEmptyStr = Annotated[str, Field(min_length=1)]


class State:
    def __init__(self, value: Any) -> None:
        self._value = copy.replace(value)
        self._previous_value = None

    @property
    def value(self) -> Any:
        return self._value

    @property
    def previous_value(self) -> Union[None, Any]:
        return self._previous_value

    def update(self, value: Any) -> None:
        self._previous_value = copy.replace(self._value)
        self._value = copy.replace(value)


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
                        _logger.exception(
                            "Execution of operation %s failed and maximum retry period %s minutes closed."
                            + "\n args: %s\n kwargs: %s",
                            operation.__name__,
                            max_delay / 60,
                            args,
                            kwargs,
                        )
                        raise RuntimeError from exc

                    delay = min(30 if delay == 0 else delay * 2, max_delay)

                    _logger.warning(
                        "Execution of operation %s failed and will be retried in %s minutes.\n args: %s\n kwargs: %s",
                        operation.__name__,
                        delay / 60,
                        args,
                        kwargs,
                    )

        return execute

    return wrapper
