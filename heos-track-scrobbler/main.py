import asyncio
import os
import sys
import traceback

import asyncio_redis
from mongoengine import connect

from last_fm.last_fm_scrobbler import LastFmScrobbler


def initialize_database_connection():
    mongo_url = "mongodb://{user}:{password}@{host}:{port}/{db}".format(
        user=os.environ.get("MONGO_USER"),
        password=os.environ.get("MONGO_PASSWORD"),
        host=os.environ.get("MONGO_HOST"),
        port=os.environ.get("MONGO_PORT"),
        db=os.environ.get("MONGO_DB"),
    )

    connect(db=os.environ.get("MONGO_DB"), alias="heosScrobbler", host=mongo_url)


async def initialize_redis_subscriber(last_fm_scrobbler):
    connection = await asyncio_redis.Connection.create(
        host=os.environ.get("REDIS_HOST"), port=int(os.environ.get("REDIS_PORT"))
    )

    subscriber = await connection.start_subscribe()
    await subscriber.subscribe([os.environ.get("REDIS_CHANNEL")])

    while True:
        reply = await subscriber.next_published()
        if reply:
            last_fm_scrobbler.update_now_playing(reply.value)
            last_fm_scrobbler.scrobble()


def main():
    try:
        initialize_database_connection()
        last_fm_scrobbler = LastFmScrobbler()
        last_fm_scrobbler.get_user()
        asyncio.get_event_loop().run_until_complete(
            initialize_redis_subscriber(last_fm_scrobbler)
        )
    except Exception:
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
