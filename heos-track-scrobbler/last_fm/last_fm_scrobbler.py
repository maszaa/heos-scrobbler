import os
import traceback

import pylast

from models.error import Error
from models.heos_played_track import HeosPlayedTrack
from models.last_fm_user import LastFmUser


class LastFmScrobbler:
    def __init__(self):
        self.creating_user = False

    def _get_user(self):
        try:
            last_fm_user = LastFmUser.objects().first()

            if last_fm_user:
                if (
                    last_fm_user.username
                    and last_fm_user.password
                    and not last_fm_user.sessionKey
                ):
                    print(
                        "Setting Last.fm session key for user {}".format(
                            last_fm_user.username
                        )
                    )
                    last_fm_user = self._set_last_fm_session_key(last_fm_user)
                    print(
                        "Set Last.fm session key for user {}".format(
                            last_fm_user.username
                        )
                    )
                elif not last_fm_user.sessionKey and (
                    not last_fm_user.username or not last_fm_user.password
                ):
                    print(
                        "Last.fm user missing username or password, set them to scrobble"
                    )
            elif self.creating_user is False:
                self.creating_user = True
                last_fm_user = LastFmUser()
                last_fm_user.save()
                print(
                    "Last.fm user does not exist in database, created a template for user - "
                    "please fill it (username and password)"
                )
                self.creating_user = False
            return last_fm_user
        except Exception:
            self.creating_user = False
            self._log_error("Error occured while getting user", traceback.format_exc())

    def _get_last_fm_network(self, last_fm_user=None):
        try:
            if last_fm_user:
                if last_fm_user.sessionKey:
                    return pylast.LastFMNetwork(
                        api_key=os.environ.get("LAST_FM_KEY"),
                        api_secret=os.environ.get("LAST_FM_SECRET"),
                        session_key=last_fm_user.sessionKey,
                    )
                return None

            return pylast.LastFMNetwork(
                api_key=os.environ.get("LAST_FM_KEY"),
                api_secret=os.environ.get("LAST_FM_SECRET"),
            )
        except Exception:
            self._log_error(
                "Error occured while getting Last.fm network", traceback.format_exc()
            )

    def _set_last_fm_session_key(self, last_fm_user):
        try:
            last_fm_network = self._get_last_fm_network()

            session_key = pylast.SessionKeyGenerator(last_fm_network).get_session_key(
                last_fm_user.username, pylast.md5(last_fm_user.password)
            )

            last_fm_user.sessionKey = session_key
            last_fm_user.password = None
            last_fm_user.save()
            return last_fm_user
        except Exception:
            self._log_error(
                "Error occured while setting Last.fm session key",
                traceback.format_exc(),
            )

    def _log_error(self, message, traceback_info):
        try:
            error = Error(
                message=message,
                error={"traceback": traceback_info.replace('"', "'").split("\n")},
            )
            error.save()
            print("{0}, id: {1}".format(error.message, error.id))
        except Exception as err:
            print(message, traceback_info, err)

    def _scrobble_length_is_valid(self, last_fm_user, heos_played_track):
        if heos_played_track.duration:
            listening_duration = (
                heos_played_track.finishedAt - heos_played_track.startedAt
            )

            if (
                listening_duration
                < last_fm_user.minimumScrobbleLength * heos_played_track.duration
            ):
                return False
            if (
                listening_duration
                > last_fm_user.maximumScrobbleLength * heos_played_track.duration
            ):
                return False
        return True

    def _required_scrobble_data_exists(self, heos_played_track, is_scrobble=False):
        if (
            not heos_played_track.title
            or not heos_played_track.artist
            or (
                is_scrobble is True
                and not heos_played_track.startedAt
                and not heos_played_track.finishedAt
            )
        ):
            return False
        return True

    def scrobble(self):
        try:
            last_fm_user = self._get_user()
            last_fm_network = self._get_last_fm_network(last_fm_user)

            heos_played_tracks = HeosPlayedTrack.objects(
                submit__track=True,
                submitStatus__track=False,
                ready__track=True,
                finishedAt__exists=True,
            )

            for heos_played_track in heos_played_tracks:
                try:
                    if (
                        last_fm_user
                        and last_fm_network
                        and self._required_scrobble_data_exists(
                            heos_played_track, is_scrobble=True
                        )
                        is True
                        and self._scrobble_length_is_valid(
                            last_fm_user, heos_played_track
                        )
                        is True
                    ):
                        last_fm_network.scrobble(
                            artist=heos_played_track.artist,
                            title=heos_played_track.title,
                            timestamp=heos_played_track.finishedAt,
                            album=heos_played_track.album,
                        )
                        heos_played_track.submitStatus.track = True

                    heos_played_track.submit.track = False
                    heos_played_track.save()
                except Exception:
                    self._log_error(
                        "Error occured while scrobbling track {artist} - {title}".format(
                            artist=heos_played_track.artist,
                            title=heos_played_track.title,
                        ),
                        traceback.format_exc(),
                    )
        except Exception:
            self._log_error(
                "Error occured while querying unscrobbled tracks",
                traceback.format_exc(),
            )

    def update_now_playing(self, track_id):
        try:
            last_fm_user = self._get_user()
            last_fm_network = self._get_last_fm_network(last_fm_user)

            heos_played_track = HeosPlayedTrack.objects(
                id=track_id,
                ready__nowPlaying=True,
                submit__nowPlaying=True,
                submitStatus__nowPlaying=False,
            ).first()

            if last_fm_user and last_fm_network and heos_played_track:
                if self._required_scrobble_data_exists(heos_played_track) is True:
                    last_fm_network.update_now_playing(
                        artist=heos_played_track.artist,
                        title=heos_played_track.title,
                        album=heos_played_track.album,
                        duration=heos_played_track.duration,
                    )

                    heos_played_track.submitStatus.nowPlaying = True
                    heos_played_track.submit.nowPlaying = False
                    heos_played_track.save()
        except Exception:
            self._log_error(
                "Error occured while updating now playing track {id}".format(
                    id=track_id
                ),
                traceback.format_exc(),
            )
