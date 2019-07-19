from mongoengine import *

class LastFmUser(Document):
  username = StringField(default="")
  password = StringField(default="")
  sessionKey = StringField()
  minimumScrobbleLength = FloatField(
    default=0.5,
    min_value=0.1,
    max_value=1.0
  )
  maximumScrobbleLength = FloatField(
    default=5.0,
    min_value=1.0
  )

  meta = {
    "collection": "lastFmUsers",
    "db_alias": "heosScrobbler"
  }
