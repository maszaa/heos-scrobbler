import os
import sys
import asyncio
import asyncio_redis
import traceback

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


@asyncio.coroutine
def initialize_redis_subscriber():
  last_fm_scrobbler = LastFmScrobbler()

  connection = yield from asyncio_redis.Connection.create(
    host=os.environ.get("REDIS_HOST"),
    port=int(os.environ.get("REDIS_PORT"))
  )

  subscriber = yield from connection.start_subscribe()
  yield from subscriber.subscribe(
    [
      os.environ.get("REDIS_CHANNEL")
    ]
  )

  while True:
    reply = yield from subscriber.next_published()
    if reply:
      last_fm_scrobbler.update_now_playing(reply.value)
      last_fm_scrobbler.scrobble()


def main():
  try:
    initialize_database_connection()
    initialize_last_fm_user()
    asyncio.get_event_loop().run_until_complete(initialize_redis_subscriber())
  except Exception:
    print(traceback.format_exc())
    sys.exit(1)


if __name__ == "__main__":
  main()
