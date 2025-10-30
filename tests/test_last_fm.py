from datetime import datetime
from typing import Optional, Type

import pytest
from pydantic import ValidationError
from pylast import LastFMNetwork, NetworkError
from pytest_mock import MockerFixture

from heos_scrobbler.last_fm import LastFmScrobbler, LastFmScrobblerRetryableScrobbleException


class TestLastFmScrobblerScrobble:
    @pytest.mark.asyncio
    async def test_scrobble_calls_scrobble_sync(self, mocker: MockerFixture) -> None:
        mocker.patch.object(
            LastFmScrobbler,
            "_create_last_fm_network",
            return_value=LastFMNetwork(api_key="x", api_secret="y", session_key="z"),
        )
        scrobble_sync_mock = mocker.patch.object(LastFmScrobbler, "_scrobble_sync", mocker.Mock())
        scrobbler = LastFmScrobbler()

        now = datetime.now()
        await scrobbler.scrobble(artist="Artist", track="Track", scrobbled_at=now, album="Album")

        scrobble_sync_mock.assert_called_once_with(
            "Artist",
            "Track",
            now,
            "Album",
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exception_from_pylast,exception_raised",
        [(NetworkError("net", None), LastFmScrobblerRetryableScrobbleException), (RuntimeError(), RuntimeError)],
    )
    async def test_scrobble_raises_on_network_error(
        self, mocker: MockerFixture, exception_from_pylast: Exception, exception_raised: Type[Exception]
    ) -> None:
        mocker.patch.object(
            LastFmScrobbler,
            "_create_last_fm_network",
            return_value=LastFMNetwork(api_key="x", api_secret="y", session_key="z"),
        )
        scrobbler = LastFmScrobbler()

        mocker.patch.object(scrobbler.last_fm_network, "scrobble", side_effect=exception_from_pylast)

        with pytest.raises(exception_raised):
            await scrobbler.scrobble(artist="A", track="T", scrobbled_at=datetime.now(), album="Al")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "artist,track,album,expect_exception",
        [
            ("Artist", "Track", "Album", None),
            ("", "Track", "Album", ValidationError),
            ("Artist", "", "Album", ValidationError),
        ],
    )
    async def test_scrobble_validation(
        self, mocker: MockerFixture, artist: str, track: str, album: str, expect_exception: Optional[Type[Exception]]
    ) -> None:
        mocker.patch.object(
            LastFmScrobbler,
            "_create_last_fm_network",
            return_value=LastFMNetwork(api_key="x", api_secret="y", session_key="z"),
        )
        scrobbler = LastFmScrobbler()

        now = datetime.now()

        if expect_exception:
            with pytest.raises(expect_exception):
                await scrobbler.scrobble(artist=artist, track=track, scrobbled_at=now, album=album)
        else:
            scrobble_mock = mocker.patch.object(scrobbler.last_fm_network, "scrobble", mocker.Mock())
            await scrobbler.scrobble(artist=artist, track=track, scrobbled_at=now, album=album)

            scrobble_mock.assert_called_once_with(
                artist=artist, title=track, timestamp=int(now.timestamp()), album=album
            )


class TestLastFmScrobblerUpdateNowPlaying:
    def test_update_now_playing_swallows_network_error(self, mocker: MockerFixture) -> None:
        mocker.patch.object(
            LastFmScrobbler,
            "_create_last_fm_network",
            return_value=LastFMNetwork(api_key="x", api_secret="y", session_key="z"),
        )
        scrobbler = LastFmScrobbler()

        mocker.patch.object(scrobbler.last_fm_network, "update_now_playing", side_effect=NetworkError("network", None))

        # Should not raise
        scrobbler.update_now_playing(artist="A", track="T", duration=123, album="Al")

    @pytest.mark.parametrize(
        "artist,track,duration,album,expect_exception",
        [
            ("Artist", "Track", 120, "Album", None),
            ("", "Track", 120, "Album", ValidationError),
            ("Artist", "", 120, "Album", ValidationError),
        ],
    )
    def test_update_now_playing_validation(
        self,
        mocker: MockerFixture,
        artist: str,
        track: str,
        duration: int,
        album: str,
        expect_exception: Optional[Type[Exception]],
    ) -> None:
        mocker.patch.object(
            LastFmScrobbler,
            "_create_last_fm_network",
            return_value=LastFMNetwork(api_key="x", api_secret="y", session_key="z"),
        )
        scrobbler = LastFmScrobbler()

        if expect_exception:
            with pytest.raises(expect_exception):
                scrobbler.update_now_playing(artist=artist, track=track, duration=duration, album=album)
        else:
            update_now_playing_mock = mocker.patch.object(
                scrobbler.last_fm_network, "update_now_playing", mocker.Mock()
            )
            scrobbler.update_now_playing(artist=artist, track=track, duration=duration, album=album)

            update_now_playing_mock.assert_called_once_with(artist=artist, title=track, duration=duration, album=album)
