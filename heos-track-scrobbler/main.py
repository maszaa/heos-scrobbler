import os
import sys

from mongoengine import connect

from models.heos_played_track import HeosPlayedTrack
from models.last_fm_user import LastFmUser
from last_fm.last_fm_scrobbler import LastFmScrobbler


def initialize_database_connection():
  mongo_url = "mongodb://{user}:{password}@{host}:{port}/{db}".format(
    user=os.environ.get("MONGO_USER"),
    password=os.environ.get("MONGO_PASSWORD"),
    host=os.environ.get("MONGO_HOST"),
    port=os.environ.get("MONGO_PORT"),
    db=os.environ.get("MONGO_DB")
  )

  connect(
    db=os.environ.get("MONGO_DB"),
    alias="heosScrobbler",
    host=mongo_url
  )


def initialize_last_fm_user():
  last_fm_user = LastFmUser.objects().first()

  if not last_fm_user:
    last_fm_user = LastFmUser()
    last_fm_user.save()
    print("Last.fm user does not exist in database, created a template for user - please fill it (username and password)")
  else:
    print("Last.fm user exists in database")


def initialize_heos_played_track_watcher():
  heos_played_tracks = HeosPlayedTrack._get_collection()
  tracks_to_submit = heos_played_tracks.watch(full_document="updateLookup")
  last_fm_scrobbler = LastFmScrobbler()

  while tracks_to_submit.alive:
    track = tracks_to_submit.try_next()
    if track:
      track = track.get("fullDocument")
      if (track.get("submit").get("nowPlaying") is True and
          track.get("ready").get("nowPlaying") is True and
          track.get("submitStatus").get("nowPlaying") is False):
        last_fm_scrobbler.update_now_playing(track)
      last_fm_scrobbler.scrobble()


def main():
  try:
    initialize_database_connection()
    initialize_last_fm_user()
    initialize_heos_played_track_watcher()
  except Exception as err:
    print(err)
    sys.exit(1)


if __name__ == "__main__":
  main()
