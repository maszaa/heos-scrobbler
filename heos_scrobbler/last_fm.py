import asyncio
from datetime import datetime
from typing import Annotated, Optional

from pydantic import Field, validate_call
from pylast import LastFMNetwork, NetworkError, SessionKeyGenerator
from pylast import md5 as pylast_md5

from config import settings


class LastFmScrobblerRetryableScrobbleException(Exception):
    pass


class LastFmScrobbler:
    NotEmptyStr = Annotated[str, Field(min_length=1)]

    def __init__(self):
        self.last_fm_network: LastFMNetwork = self._create_last_fm_network()

    @staticmethod
    def _create_last_fm_network() -> LastFMNetwork:
        temporary_last_fm_network = LastFMNetwork(
            api_key=settings.last_fm.api_key, api_secret=settings.last_fm.api_secret
        )
        session_key = SessionKeyGenerator(temporary_last_fm_network).get_session_key(
            username=settings.last_fm.username, password_hash=pylast_md5(settings.last_fm.password)
        )

        if session_key is None:
            raise RuntimeError("Last.fm session key can't be None")

        return LastFMNetwork(
            api_key=settings.last_fm.api_key,
            api_secret=settings.last_fm.api_secret,
            session_key=session_key,
        )

    @validate_call
    async def scrobble(
        self, artist: NotEmptyStr, track: NotEmptyStr, scrobbled_at: datetime, album: Optional[str]
    ) -> None:
        coroutine = asyncio.to_thread(self._scrobble_sync, artist, track, scrobbled_at, album)
        task = asyncio.create_task(coroutine)
        await task

    @validate_call
    def update_now_playing(self, artist: NotEmptyStr, track: NotEmptyStr, duration: int, album: Optional[str]) -> None:
        try:
            self.last_fm_network.update_now_playing(
                artist=artist,
                title=track,
                duration=duration,
                album=album,
            )
        except NetworkError:
            # No need to retry as now playing track is relevant only for the duration of it
            pass

    def _scrobble_sync(
        self, artist: NotEmptyStr, track: NotEmptyStr, scrobbled_at: datetime, album: Optional[str]
    ) -> None:
        try:
            self.last_fm_network.scrobble(
                artist=artist,
                title=track,
                timestamp=int(scrobbled_at.timestamp()),
                album=album,
            )
        except NetworkError as exc:
            raise LastFmScrobblerRetryableScrobbleException from exc
