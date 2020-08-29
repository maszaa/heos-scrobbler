from mongoengine import *


class Submit(EmbeddedDocument):
    nowPlaying = BooleanField(default=False)
    track = BooleanField(default=False)


class HeosPlayedTrack(Document):
    type = StringField()
    source = StringField()
    title = StringField()
    artist = StringField()
    album = StringField()
    duration = FloatField()
    imageUrl = StringField()
    startedAt = IntField(min_value=0)
    finishedAt = IntField(min_value=0)
    ready = EmbeddedDocumentField(Submit)
    submit = EmbeddedDocumentField(Submit)
    submitStatus = EmbeddedDocumentField(Submit)
    player = StringField()
    v = IntField(db_field="__v")

    meta = {"collection": "heosPlayedTracks", "db_alias": "heosScrobbler"}
