import os

import pylast
from mongoengine import connect

from models.heos_played_track import HeosPlayedTrack
from models.last_fm_user import LastFmUser
from last_fm.last_fm_utils import get_last_fm_network, set_last_fm_session_key
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


def initialize_last_fm_scrobbling():
  last_fm_user = LastFmUser.objects().first()

  if not last_fm_user:
    last_fm_user = LastFmUser()
    last_fm_user.save()
    print("Last.fm user does not exist in database, created a template for user - please fill it (username and password)")
  else:
    print("Last.fm user exists in database")

  if last_fm_user.username and last_fm_user.password and not last_fm_user.sessionKey:
    last_fm_user = set_last_fm_session_key(last_fm_user.username, last_fm_user.password)
    print("Set session key for Last.fm user")

  if last_fm_user.sessionKey:
    last_fm_network = get_last_fm_network(session_key=last_fm_user.sessionKey)
    print("Initializing Last.fm scrobbler")
    last_fm_scrobbler = LastFmScrobbler(last_fm_network, last_fm_user)
    print("Initialized Last.fm scrobbler")
    return last_fm_scrobbler

  print("Last.fm user missing username and password, please set them")


def initialize_collection_watchers(last_fm_scrobbler):
  last_fm_users = LastFmUser._get_collection()
  last_fm_users_to_watch = last_fm_users.watch(full_document="updateLookup")
  tracks_to_submit = None

  if last_fm_scrobbler:
    heos_played_tracks = HeosPlayedTrack._get_collection()
    tracks_to_submit = heos_played_tracks.watch(full_document="updateLookup")

  while True:
    while last_fm_users_to_watch.alive:
      last_fm_user = last_fm_users_to_watch.try_next()
      if last_fm_user:
        print("Noticed changes in Last.fm user, updating scrobbler")
        last_fm_scrobbler = initialize_last_fm_scrobbling()
        initialize_collection_watchers(last_fm_scrobbler)
      break

    while tracks_to_submit and tracks_to_submit.alive:
      track = tracks_to_submit.try_next()
      if track:
        track = track.get("fullDocument")
        if track.get("submit").get("nowPlaying") is True and track.get("submitStatus").get("nowPlaying") is False:
          last_fm_scrobbler.update_now_playing(track)
        last_fm_scrobbler.scrobble()
      break


def main():
  initialize_database_connection()
  last_fm_scrobbler = initialize_last_fm_scrobbling()
  initialize_collection_watchers(last_fm_scrobbler)


if __name__ == "__main__":
  main()
