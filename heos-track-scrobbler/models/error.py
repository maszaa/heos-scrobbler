from mongoengine import *
import datetime

class Error(Document):
  type = StringField()
  source = StringField(default="heos-track-scrobbler")
  message = StringField()
  info = DictField()
  date = DateTimeField(default=datetime.datetime.utcnow)
  v = IntField(db_field="__v")

  meta = {
    "collection": "errors",
    "db_alias": "heosScrobbler"
  }