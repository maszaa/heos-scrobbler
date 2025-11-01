import dataclasses
import pprint
from datetime import datetime
from typing import Any, Optional
from unittest.mock import Mock

import pytest
from faker import Faker
from pyheos import Heos, HeosNowPlayingMedia, HeosPlayer, LineOutLevelType, MediaType, NetworkType
from pyheos import const as HeosConstants
from pylast import LastFMNetwork
from pytest_mock import MockerFixture

from config import settings
from heos_scrobbler.heos import (
    HeosDeviceDiscoveryProtocol,
    HeosScrobbler,
    _create_on_heos_player_event_callback,
    _discover_heos_devices,
    initialize_heos_scrobbling,
)
from heos_scrobbler.last_fm import LastFmScrobbler
from tests.util import integration_test

HeosIpsAndPlayers = tuple[list[str | None], list[dict[str, HeosPlayer] | dict[Any, Any]]]


@pytest.fixture
def heos() -> Heos:
    return Mock(spec=Heos)


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
def heos_player(faker: Faker, heos: Heos, heos_now_playing_media: HeosNowPlayingMedia) -> HeosPlayer:
    return HeosPlayer(
        name=faker.last_name(),
        player_id=faker.random_int(),
        ip_address=faker.ipv4_private(),
        model=f"HEOS {faker.company()}",
        serial=faker.uuid4(),
        version=str(faker.random_int()),
        supported_version=True,
        network=NetworkType.WIRED,
        line_out=LineOutLevelType.FIXED,
        heos=heos,
        now_playing_media=heos_now_playing_media,
    )


@pytest.fixture
def heos_ips_and_players(faker: Faker, heos: Heos, heos_player: HeosPlayer) -> HeosIpsAndPlayers:
    second_player = dataclasses.replace(
        heos_player, player_id=faker.random_int(), ip_address=faker.ipv4_private(), heos=heos
    )
    third_player = dataclasses.replace(
        heos_player, player_id=faker.random_int(), ip_address=faker.ipv4_private(), heos=heos
    )
    fourth_player = dataclasses.replace(
        heos_player, player_id=faker.random_int(), ip_address=faker.ipv4_private(), heos=heos
    )

    return (
        [heos_player.ip_address, second_player.ip_address, third_player.ip_address, fourth_player.ip_address],
        [
            {
                f"{heos_player.player_id}": heos_player,
                f"{second_player.player_id}": second_player,
                f"{third_player.player_id}": third_player,
                f"{fourth_player.player_id}": fourth_player,
            },
            {
                f"{second_player.player_id}": second_player,
            },
            {
                f"{heos_player.player_id}": heos_player,
                f"{second_player.player_id}": second_player,
                f"{fourth_player.player_id}": fourth_player,
            },
            {},
        ],
    )


@pytest.fixture
def last_fm_scrobbler(mocker: MockerFixture, last_fm_network: LastFMNetwork) -> LastFmScrobbler:
    mocker.patch.object(
        LastFmScrobbler,
        "_create_last_fm_network",
        return_value=last_fm_network,
    )
    return LastFmScrobbler()


@pytest.mark.asyncio
async def test_callback_created_for_heos_player_event_calls_scrobbler(
    mocker: MockerFixture, heos_player: HeosPlayer, last_fm_scrobbler: LastFmScrobbler
) -> None:
    scrobbler = HeosScrobbler(last_fm_scrobbler=last_fm_scrobbler)

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


@pytest.mark.asyncio
async def tests_initialize_heos_scrobbling(
    mocker: MockerFixture, heos: Heos, heos_ips_and_players: HeosIpsAndPlayers, last_fm_network: LastFMNetwork
) -> None:
    discover_heos_devices_mock = mocker.patch(
        "heos_scrobbler.heos._discover_heos_devices", mocker.AsyncMock(return_value=heos_ips_and_players[0])
    )
    last_fm_network_mock = mocker.patch.object(
        LastFmScrobbler,
        "_create_last_fm_network",
        return_value=last_fm_network,
    )
    heos_create_and_connect_mock = mocker.patch.object(Heos, "create_and_connect", mocker.AsyncMock(return_value=heos))
    heos_get_players_mock = mocker.patch.object(
        heos, "get_players", mocker.AsyncMock(side_effect=heos_ips_and_players[1])
    )
    create_on_heos_player_event_callback_mock = mocker.patch(
        "heos_scrobbler.heos._create_on_heos_player_event_callback", mocker.Mock()
    )

    await initialize_heos_scrobbling()

    discover_heos_devices_mock.assert_awaited_once()

    last_fm_network_mock.assert_called_once()

    assert heos_create_and_connect_mock.await_count == 4
    pprint.pprint(heos_create_and_connect_mock.call_args_list)
    assert [call.args[0] for call in heos_create_and_connect_mock.call_args_list] == heos_ips_and_players[0]

    assert heos_get_players_mock.await_count == 4

    assert create_on_heos_player_event_callback_mock.call_count == 2
    pprint.pprint(create_on_heos_player_event_callback_mock.call_args_list)
    assert {
        call.kwargs.get("heos_player").__dict__.get("player_id")
        for call in create_on_heos_player_event_callback_mock.call_args_list
    } == {
        player.player_id
        for player in [
            next((value for key, value in dict_item.items() if key == str(value.player_id)), None)
            for dict_item in heos_ips_and_players[1]
        ]
        if player is not None
    }


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
        self, mocker: MockerFixture, last_fm_scrobbler: LastFmScrobbler, heos_now_playing_media: HeosNowPlayingMedia
    ) -> None:
        scrobble_sync_mock = mocker.patch.object(last_fm_scrobbler, "_scrobble_sync", mocker.Mock())

        scrobbler = HeosScrobbler(last_fm_scrobbler=last_fm_scrobbler)

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
        self, mocker: MockerFixture, last_fm_scrobbler: LastFmScrobbler, heos_now_playing_media: HeosNowPlayingMedia
    ) -> None:
        update_now_playing_mock = mocker.patch.object(last_fm_scrobbler, "update_now_playing", mocker.Mock())

        scrobbler = HeosScrobbler(last_fm_scrobbler=last_fm_scrobbler)

        scrobbler.update_now_playing(heos_track=heos_now_playing_media)

        assert heos_now_playing_media.duration is not None

        update_now_playing_mock.assert_called_once_with(
            artist=heos_now_playing_media.artist,
            track=heos_now_playing_media.song,
            duration=heos_now_playing_media.duration // 1000,
            album=heos_now_playing_media.album,
        )


@integration_test
@pytest.mark.asyncio
async def test_discover_heos_devices(mocker: MockerFixture) -> None:
    discover_heos_devices_mock = mocker.spy(HeosDeviceDiscoveryProtocol, "response_received")

    result = await _discover_heos_devices()

    assert len(result) == len(discover_heos_devices_mock.call_args_list)
    assert set(result) == set([call.args[2][0] for call in discover_heos_devices_mock.call_args_list])
