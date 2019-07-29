import traceback

from models.heos_played_track import HeosPlayedTrack
from models.error import Error


class LastFmScrobbler(object):
  def __init__(self, last_fm_network, last_fm_user):
    self.last_fm_network = last_fm_network
    self.last_fm_user = last_fm_user

  def _log_error(self, message, traceback_info):
    try:
      error = Error(
        message=message,
        error={str(key): value.strip() for (key, value) in traceback_info.split("\n")}
      )
      error.save()
      print("{0}, id: {1}".format(error.message, error.id))
    except Exception as err:
      print(err)

  def _scrobble_length_is_valid(self, heos_played_track):
    if heos_played_track.duration:
      listening_duration = (heos_played_track.finishedAt - heos_played_track.startedAt)

      if listening_duration < self.last_fm_user.minimumScrobbleLength * heos_played_track.duration:
        return False
      if listening_duration > self.last_fm_user.maximumScrobbleLength * heos_played_track.duration:
        return False
    return True

  def _required_scrobble_data_exists(self, heos_played_track, is_scrobble=False):
    if (not heos_played_track.title or
        not heos_played_track.artist or
        (is_scrobble is True and not heos_played_track.startedAt and not heos_played_track.finishedAt)):
      return False
    return True

  def scrobble(self):
    try:
      heos_played_tracks = HeosPlayedTrack.objects(
        submit__track=True,
        submitStatus__track=False,
        ready__track=True,
        finishedAt__exists=True
      )

      for heos_played_track in heos_played_tracks:
        try:
          if (self._required_scrobble_data_exists(heos_played_track, is_scrobble=True) is True and
              self._scrobble_length_is_valid(heos_played_track) is True):
            self.last_fm_network.scrobble(
              artist=heos_played_track.artist,
              title=heos_played_track.title,
              timestamp=heos_played_track.finishedAt,
              album=heos_played_track.album
            )
            heos_played_track.submitStatus.track = True

          heos_played_track.submit.track = False
          heos_played_track.save()
        except Exception:
          self._log_error(
            "Error occured while scrobbling track {artist} - {title}".format(
              artist=heos_played_track.artist,
              title=heos_played_track.title
            ),
            traceback.format_exc()
          )
    except Exception:
      self._log_error(
        "Error occured while querying unscrobbled tracks",
        traceback.format_exc()
      )

  def update_now_playing(self, data):
    try:
      heos_played_track = HeosPlayedTrack.objects(id=data.get("_id")).first()

      if self._required_scrobble_data_exists(heos_played_track) is True:
        self.last_fm_network.update_now_playing(
          artist=heos_played_track.artist,
          title=heos_played_track.title,
          album=heos_played_track.album
        )

        heos_played_track.submitStatus.nowPlaying = True

      heos_played_track.submit.nowPlaying = False
      heos_played_track.save()
    except Exception:
      self._log_error(
        "Error occured while updating now playing track {artist} - {title}".format(
          artist=data.get("artist"),
          title=data.get("title")
        ),
        traceback.format_exc()
      )
