import asyncio
import dataclasses
import pprint
import socket
import sys
from datetime import datetime
from logging import Logger, getLogger
from typing import Any, Callable, Coroutine, Final, Union

from pydantic import ValidationError
from pyheos import Heos, HeosNowPlayingMedia, HeosPlayer, MediaType
from pyheos import const as HeosConstants
from ssdp import network
from ssdp.aio import SSDP
from ssdp.messages import SSDPRequest, SSDPResponse

from config import settings
from heos_scrobbler.last_fm import LastFmScrobbler, LastFmScrobblerRetryableScrobbleException
from heos_scrobbler.util import State, retry

_logger: Final[Logger] = getLogger(__name__)


class HeosDeviceDiscoveryProtocol(SSDP):
    def __init__(self):
        self.heos_device_ips: list[str] = []
        super().__init__()

    def response_received(self, response: SSDPResponse, addr: Any) -> None:
        _logger.debug("SSDP response received:\n%s\n%s", addr, response)
        self.heos_device_ips.append(str(addr[0]))

    def request_received(self, request: SSDPRequest, addr: Any) -> None:
        _logger.debug("SSDP request received:\n%s\n%s", addr, request)
        pass

    def connection_lost(self, exc: Union[Exception, None]) -> None:
        _logger.debug("SSDP connection closed:\n%s", exc)
        pass


class HeosScrobbler:
    def __init__(self, last_fm_scrobbler: LastFmScrobbler):
        self.last_fm_scrobbler: LastFmScrobbler = last_fm_scrobbler
        self.heos_track_for_scrobbling: State = State(HeosNowPlayingMedia())
        self.heos_track_for_now_playing: State = State(HeosNowPlayingMedia())

    async def scrobble(self, heos_track: HeosNowPlayingMedia, scrobbled_at: datetime) -> None:
        self.heos_track_for_scrobbling.update(heos_track)

        if self.heos_track_for_scrobbling.previous_value is not None:
            await self._scrobble(
                heos_track=dataclasses.replace(self.heos_track_for_scrobbling.previous_value), scrobbled_at=scrobbled_at
            )

    def update_now_playing(self, heos_track: HeosNowPlayingMedia) -> None:
        if self.heos_track_for_now_playing.value.media_id != heos_track.media_id and heos_track.duration:
            self.heos_track_for_now_playing.update(heos_track)
            self._update_now_playing(heos_track=dataclasses.replace(self.heos_track_for_now_playing.value))

    def handle_progress_for_track_to_be_scrobbled(self, heos_track: HeosNowPlayingMedia) -> None:
        if (
            self.heos_track_for_scrobbling.value.media_id is None
            or self.heos_track_for_scrobbling.value.media_id == heos_track.media_id
        ) and heos_track.current_position:
            self.heos_track_for_scrobbling.update(heos_track)

    @retry(max_delay=settings.retry_scrobble_for_hours * 60 * 60, retry_on=LastFmScrobblerRetryableScrobbleException)
    async def _scrobble(self, heos_track: HeosNowPlayingMedia, scrobbled_at: datetime) -> None:
        if self.can_scrobble_track(heos_track=heos_track):
            try:
                await self.last_fm_scrobbler.scrobble(
                    artist=heos_track.artist or "",
                    track=heos_track.song or "",
                    scrobbled_at=scrobbled_at,
                    album=heos_track.album or "",
                )
            except ValidationError:
                _logger.info(
                    "Track %s/%s: %s not suitable for scrobbling", heos_track.artist, heos_track.album, heos_track.song
                )

    def _update_now_playing(self, heos_track: HeosNowPlayingMedia) -> None:
        if HeosScrobbler.cap_update_now_playing(heos_track=heos_track):
            try:
                self.last_fm_scrobbler.update_now_playing(
                    artist=heos_track.artist or "",
                    track=heos_track.song or "",
                    duration=heos_track.duration or 0,
                    album=heos_track.album or "",
                )
            except ValidationError:
                _logger.info(
                    "Track %s/%s: %s not suitable for now playing", heos_track.artist, heos_track.album, heos_track.song
                )

    @staticmethod
    def cap_update_now_playing(heos_track: HeosNowPlayingMedia) -> bool:
        return heos_track.type is not None and heos_track.type == MediaType.SONG and heos_track.duration is not None

    @staticmethod
    def can_scrobble_track(heos_track: HeosNowPlayingMedia) -> bool:
        return (
            HeosScrobbler.cap_update_now_playing(heos_track=heos_track)
            and heos_track.current_position is not None
            and heos_track.current_position >= heos_track.duration * settings.scrobble_length_min_portion
        )


async def _discover_heos_devices() -> list[str]:
    loop = asyncio.get_event_loop()

    # On Windows local_addr is required, otherwise "OSError: [WinError 10022] An invalid argument was supplied" occurs
    # See: https://github.com/codingjoe/ssdp/issues/85
    if sys.platform == "win32":
        transport, protocol = await loop.create_datagram_endpoint(
            HeosDeviceDiscoveryProtocol, family=socket.AF_INET, local_addr=(socket.gethostname(), 0)
        )
    else:
        transport, protocol = await loop.create_datagram_endpoint(HeosDeviceDiscoveryProtocol, family=socket.AF_INET)

    m_search_request = SSDPRequest(
        "M-SEARCH",
        headers={
            "HOST": f"{network.MULTICAST_ADDRESS_IPV4}:{network.PORT:d}",
            "MAN": '"ssdp:discover"',
            "MX": str(settings.heos.ssdp.mx),
            "ST": settings.heos.ssdp.st,
        },
    )

    m_search_request.sendto(transport, (network.MULTICAST_ADDRESS_IPV4, network.PORT))

    try:
        await asyncio.sleep(settings.heos.ssdp.mx)
    finally:
        transport.close()

    return protocol.heos_device_ips


def _create_on_heos_player_event_callback(
    heos_player: HeosPlayer, heos_scrobbler: HeosScrobbler
) -> Callable[[str], Coroutine[Any, Any, None]]:
    async def callback(heos_event: str) -> None:
        heos_track = heos_player.now_playing_media

        if heos_event == HeosConstants.EVENT_PLAYER_NOW_PLAYING_CHANGED:
            await heos_scrobbler.scrobble(heos_track=heos_track, scrobbled_at=datetime.now())
        elif heos_event == HeosConstants.EVENT_PLAYER_NOW_PLAYING_PROGRESS:
            # After EVENT_PLAYER_NOW_PLAYING_CHANGED track duration is 0
            # We need to update duration here for the next track to be scrobbled
            # so that we can ensure it's been listened enough
            heos_scrobbler.handle_progress_for_track_to_be_scrobbled(heos_track)
            # We need to update now playing here to get proper duration down the line
            heos_scrobbler.update_now_playing(heos_track)

    return callback


async def initialize_heos_scrobbling() -> None:
    _logger.info("Discovering HEOS devices, waiting responses for %s seconds...", settings.heos.ssdp.mx)

    heos_device_ips = await _discover_heos_devices()

    if len(heos_device_ips) == 0:
        _logger.warning("No HEOS devices found!")
        exit(1)

    _logger.info("Found HEOS devices with following IP addresses:\n%s", heos_device_ips)

    last_fm_scrobbler = LastFmScrobbler()

    for heos_device_ip in heos_device_ips:
        heos = await Heos.create_and_connect(heos_device_ip, auto_reconnect=settings.heos.auto_reconnect)

        heos_players = await heos.get_players()
        _logger.info("HEOS device with IP %s has players\n%s", heos_device_ip, pprint.pformat(heos_players))

        for heos_player in heos_players.values():
            scrobbler = HeosScrobbler(last_fm_scrobbler=last_fm_scrobbler)
            heos_player.add_on_player_event(
                _create_on_heos_player_event_callback(heos_player=heos_player, heos_scrobbler=scrobbler)
            )
            _logger.info(
                "Listening player events of HEOS player with id %s and IP %s", heos_player.player_id, heos_device_ip
            )
