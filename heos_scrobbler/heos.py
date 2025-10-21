import asyncio
import dataclasses
import pprint
import socket
from logging import getLogger
from typing import Callable

from pydantic import ValidationError
from pyheos import Heos, HeosNowPlayingMedia, HeosPlayer
from pyheos import const as HeosConstants
from ssdp import messages, network
from ssdp.aio import SSDP

from config import settings
from heos_scrobbler.last_fm import LastFmScrobbler

logger = getLogger(__name__)


class HeosDeviceDiscoveryProtocol(SSDP):
    def __init__(self):
        self.heos_device_ips = []
        super().__init__()

    def response_received(self, response, addr):
        self.heos_device_ips.append(addr[0])

    def request_received(self, request, addr):
        pass

    def connection_lost(self, exc):
        pass


class HeosScrobbler:
    def __init__(self, heos_player: HeosPlayer, last_fm_scrobbler: LastFmScrobbler):
        self.heos_player = heos_player
        self.last_fm_scrobbler: LastFmScrobbler = last_fm_scrobbler
        self.current_heos_track: HeosNowPlayingMedia = HeosNowPlayingMedia()

    def scrobble(self, heos_track: HeosNowPlayingMedia) -> None:
        if self.current_heos_track.media_id != heos_track.media_id:
            if self._can_scrobble_current_track():
                self._scrobble(dataclasses.replace(self.current_heos_track))
            self.current_heos_track = dataclasses.replace(heos_track)

    def update_now_playing(self, heos_track: HeosNowPlayingMedia) -> None:
        try:
            self.last_fm_scrobbler.update_now_playing(
                artist=heos_track.artist or "",
                track=heos_track.song or "",
                album=heos_track.album or "",
            )
        except ValidationError:
            logger.info(
                "Track %s/%s: %s not suitable for now playing", heos_track.artist, heos_track.album, heos_track.song
            )

    def update_track_progress(self, heos_track: HeosNowPlayingMedia) -> None:
        if (
            self.current_heos_track.media_id is None or self.current_heos_track.media_id == heos_track.media_id
        ) and heos_track.current_position:
            self.current_heos_track = dataclasses.replace(heos_track)

    def _scrobble(self, heos_track: HeosNowPlayingMedia) -> None:
        try:
            self.last_fm_scrobbler.scrobble(
                artist=heos_track.artist or "",
                track=heos_track.song or "",
                album=heos_track.album or "",
            )
        except ValidationError:
            logger.info(
                "Track %s/%s: %s not suitable for scrobbling", heos_track.artist, heos_track.album, heos_track.song
            )

    def _can_scrobble_current_track(self) -> bool:
        return (
            self.current_heos_track.duration is not None
            and self.current_heos_track.current_position is not None
            and self.current_heos_track.current_position
            >= self.current_heos_track.duration * settings.scrobble_length_min_portion
        )


async def _discover_heos_devices() -> list[str]:
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        HeosDeviceDiscoveryProtocol, family=socket.AF_INET, local_addr=(socket.gethostname(), 0)
    )

    m_search_request = messages.SSDPRequest(
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
) -> Callable[[str], None]:
    def callback(heos_event: str) -> None:
        if heos_event == HeosConstants.EVENT_PLAYER_NOW_PLAYING_CHANGED:
            heos_scrobbler.update_now_playing(heos_player.now_playing_media)
            heos_scrobbler.scrobble(heos_player.now_playing_media)
        elif heos_event == HeosConstants.EVENT_PLAYER_NOW_PLAYING_PROGRESS:
            heos_scrobbler.update_track_progress(heos_player.now_playing_media)

    return callback


async def initialize_heos_scrobbling() -> None:
    logger.info("Discovering HEOS devices, waiting for %s seconds", settings.heos.ssdp.mx)

    heos_device_ips = await _discover_heos_devices()

    if len(heos_device_ips) == 0:
        logger.warning("No HEOS devices found")
        exit(1)

    logger.info("Found HEOS devices with following IP addresses: %s", heos_device_ips)

    last_fm_scrobbler = LastFmScrobbler()

    for heos_device_ip in heos_device_ips:
        heos = await Heos.create_and_connect(heos_device_ip, auto_reconnect=settings.heos.auto_reconnect)

        heos_players = await heos.get_players()
        logger.info("HEOS device with IP %s has players %s", heos_device_ip, pprint.pformat(heos_players))

        for heos_player in heos_players.values():
            scrobbler = HeosScrobbler(heos_player=heos_player, last_fm_scrobbler=last_fm_scrobbler)
            heos_player.add_on_player_event(
                _create_on_heos_player_event_callback(heos_player=heos_player, heos_scrobbler=scrobbler)
            )
            logger.info(
                "HEOS player with id %s and ip %s listening player events", heos_player.player_id, heos_device_ip
            )
