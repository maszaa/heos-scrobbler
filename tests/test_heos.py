import dataclasses
import os
from datetime import datetime
from typing import Optional

import pytest
from faker import Faker
from pyheos import HeosNowPlayingMedia, HeosPlayer, LineOutLevelType, MediaType, NetworkType
from pyheos import const as HeosConstants
from pylast import LastFMNetwork
from pytest_mock import MockerFixture

from config import settings
from heos_scrobbler.heos import (
    HeosDeviceDiscoveryProtocol,
    HeosScrobbler,
    _create_on_heos_player_event_callback,
    _discover_heos_devices,
)
from heos_scrobbler.last_fm import LastFmScrobbler

skip_in_ci = pytest.mark.skipif(bool(os.getenv("CI", False)), reason="SSDP discovery test disabled in CI")


@pytest.fixture
def heos_now_playing_media(faker: Faker) -> HeosNowPlayingMedia:
    duration = faker.random_int(min=10_000, max=1_000_000)
    return HeosNowPlayingMedia(
        media_id=faker.uuid4(),
        artist=faker.name(),
        song=faker.name(),
        album=faker.name(),
        type=MediaType.SONG,
        duration=duration,
        current_position=int(duration * settings.scrobble_length_min_portion),
    )


@pytest.fixture
def heos_player(faker: Faker, heos_now_playing_media: HeosNowPlayingMedia) -> HeosPlayer:
    heos_player = HeosPlayer(
        name=faker.last_name(),
        player_id=faker.random_int(),
        ip_address=faker.ipv4_private(),
        model=f"HEOS {faker.company()}",
        serial=faker.uuid4(),
        version=str(faker.random_int()),
        supported_version=True,
        network=NetworkType.WIRED,
        line_out=LineOutLevelType.FIXED,
    )
    heos_player.now_playing_media = heos_now_playing_media
    return heos_player


@pytest.fixture
def lastfm_scrobbler(faker: Faker, mocker: MockerFixture) -> LastFmScrobbler:
    mocker.patch.object(
        LastFmScrobbler,
        "_create_last_fm_network",
        return_value=LastFMNetwork(
            api_key=faker.random_letter(), api_secret=faker.random_letter(), session_key=faker.random_letter()
        ),
    )
    return LastFmScrobbler()


@pytest.mark.asyncio
async def test_callback_created_for_heos_player_event_calls_scrobbler(
    mocker: MockerFixture, heos_player: HeosPlayer, lastfm_scrobbler: LastFmScrobbler
) -> None:
    scrobbler = HeosScrobbler(last_fm_scrobbler=lastfm_scrobbler)

    scrobble_mock = mocker.patch.object(scrobbler, "scrobble", mocker.AsyncMock())
    handle_progress_for_track_to_be_scrobbled_mock = mocker.patch.object(
        scrobbler, "handle_progress_for_track_to_be_scrobbled", mocker.Mock()
    )
    update_now_playing_mock = mocker.patch.object(scrobbler, "update_now_playing", mocker.Mock())

    callback = _create_on_heos_player_event_callback(heos_player=heos_player, heos_scrobbler=scrobbler)

    await callback(HeosConstants.EVENT_PLAYER_NOW_PLAYING_CHANGED)
    scrobble_mock.assert_awaited()
    handle_progress_for_track_to_be_scrobbled_mock.assert_not_called()
    update_now_playing_mock.assert_not_called()

    await callback(HeosConstants.EVENT_PLAYER_NOW_PLAYING_PROGRESS)
    handle_progress_for_track_to_be_scrobbled_mock.assert_called()
    update_now_playing_mock.assert_called()

    scrobble_mock.assert_awaited_once()


@skip_in_ci
@pytest.mark.asyncio
async def test_discover_heos_devices(mocker: MockerFixture) -> None:
    discover_heos_devices_mock = mocker.spy(HeosDeviceDiscoveryProtocol, "response_received")

    result = await _discover_heos_devices()

    assert len(result) == len(discover_heos_devices_mock.call_args_list)
    assert set(result) == set([call.args[2][0] for call in discover_heos_devices_mock.call_args_list])


class TestHeosScrobbler:
    @pytest.mark.parametrize(
        "media_type,duration,expected",
        [
            (None, None, False),
            (MediaType.SONG, None, False),
            (MediaType.SONG, 200_000, True),
            (MediaType.ALBUM, 200_000, False),
        ],
    )
    def test_cap_update_now_playing(self, media_type: MediaType, duration: Optional[int], expected: bool) -> None:
        media = HeosNowPlayingMedia(type=media_type, duration=duration)

        assert HeosScrobbler.cap_update_now_playing(media) == expected

    @pytest.mark.parametrize(
        "media_type,duration,current_position,expected",
        [
            (None, None, None, False),
            (MediaType.SONG, None, None, False),
            (MediaType.SONG, 180_000, None, False),
            (MediaType.SONG, 180_000, int(180_000 * (settings.scrobble_length_min_portion - 0.1)), False),
            (MediaType.SONG, 180_000, int(180_000 * settings.scrobble_length_min_portion), True),
            (MediaType.ALBUM, 180_000, 180_000, False),
        ],
    )
    def test_can_scrobble_track(
        self, media_type: MediaType, duration: Optional[int], current_position: Optional[int], expected: bool
    ) -> None:
        media = HeosNowPlayingMedia(type=media_type, duration=duration, current_position=current_position)

        assert HeosScrobbler.can_scrobble_track(media) == expected

    @pytest.mark.asyncio
    async def test_scrobble_calls_lastfm_scrobbler(
        self, mocker: MockerFixture, lastfm_scrobbler: LastFmScrobbler, heos_now_playing_media: HeosNowPlayingMedia
    ) -> None:
        scrobble_sync_mock = mocker.patch.object(lastfm_scrobbler, "_scrobble_sync", mocker.Mock())

        scrobbler = HeosScrobbler(last_fm_scrobbler=lastfm_scrobbler)

        scrobbler.handle_progress_for_track_to_be_scrobbled(heos_now_playing_media)

        now = datetime.now()

        await scrobbler.scrobble(
            heos_track=dataclasses.replace(heos_now_playing_media, media_id="abc"), scrobbled_at=now
        )

        scrobble_sync_mock.assert_called_with(
            heos_now_playing_media.artist,
            heos_now_playing_media.song,
            now,
            heos_now_playing_media.album,
        )

    def test_update_now_playing_calls_lastfm_scrobbler(
        self, mocker: MockerFixture, lastfm_scrobbler: LastFmScrobbler, heos_now_playing_media: HeosNowPlayingMedia
    ) -> None:
        update_now_playing_mock = mocker.patch.object(lastfm_scrobbler, "update_now_playing", mocker.Mock())

        scrobbler = HeosScrobbler(last_fm_scrobbler=lastfm_scrobbler)

        scrobbler.update_now_playing(heos_track=heos_now_playing_media)

        assert heos_now_playing_media.duration is not None

        update_now_playing_mock.assert_called_once_with(
            artist=heos_now_playing_media.artist,
            track=heos_now_playing_media.song,
            duration=heos_now_playing_media.duration // 1000,
            album=heos_now_playing_media.album,
        )
