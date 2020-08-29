const mongoose = require("mongoose");

const redis = require("redis").createClient({
  host: process.env.REDIS_HOST,
  port: process.env.REDIS_PORT,
});

const Schema = mongoose.Schema;

const heosPlayedTrackSchema = new Schema({
  type: String,
  source: String,
  title: String,
  artist: String,
  album: String,
  duration: Number,
  imageUrl: String,
  startedAt: Number,
  finishedAt: Number,
  ready: {
    nowPlaying: {
      type: Boolean,
      default: false,
    },
    track: {
      type: Boolean,
      default: false,
    },
  },
  submit: {
    nowPlaying: {
      type: Boolean,
      default: false,
    },
    track: {
      type: Boolean,
      default: false,
    },
  },
  submitStatus: {
    nowPlaying: {
      type: Boolean,
      default: false,
    },
    track: {
      type: Boolean,
      default: false,
    },
  },
  player: String,
});

heosPlayedTrackSchema.post("save", (track) => {
  if (track.ready.nowPlaying) {
    redis.publish(process.env.REDIS_CHANNEL, track._id.toString());
  }
});

module.exports = mongoose.model(
  "HeosPlayedTrack",
  heosPlayedTrackSchema,
  "heosPlayedTracks"
);
