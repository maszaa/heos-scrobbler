import asyncio
from dataclasses import dataclass

import pytest
from pytest_mock import MockerFixture

from heos_scrobbler.util import State, retry


def test_state() -> None:
    @dataclass
    class MyData:
        a: int = 0

    s = State(value=MyData(a=1))
    assert s.previous_value is None

    first_value = s.value
    new_value = MyData(a=2)

    s.update(new_value)
    assert s.value is not first_value
    assert s.previous_value is not None


class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_decorator_retries_and_succeeds(self, mocker: MockerFixture) -> None:
        mocker.patch.object(asyncio, "sleep", mocker.AsyncMock())

        attempts = 0

        @retry(max_delay=100, retry_on=ValueError)
        async def sometimes_fails() -> bool:
            nonlocal attempts

            attempts += 1
            if attempts < 3:
                raise ValueError()

            return True

        result = await sometimes_fails()
        assert result is True
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_retry_decorator_retries_but_does_not_succeed_due_to_max_delay_encountered(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(asyncio, "sleep", mocker.AsyncMock())

        attempts = 0

        @retry(max_delay=5, retry_on=ValueError)
        async def always_fails() -> None:
            nonlocal attempts

            attempts += 1
            raise ValueError()

        with pytest.raises(RuntimeError):
            await always_fails()

        assert attempts == 2

    @pytest.mark.asyncio
    async def test_retry_decorator_does_not_retry(self, mocker: MockerFixture) -> None:
        mocker.patch.object(asyncio, "sleep", mocker.AsyncMock())

        @retry(max_delay=5, retry_on=ValueError)
        async def always_fails() -> None:
            raise AttributeError()

        with pytest.raises(AttributeError):
            await always_fails()
