const mongoose = require('mongoose');
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
      default: false
    },
    track: {
      type: Boolean,
      default: false
    }
  },
  submit: {
    nowPlaying: {
      type: Boolean,
      default: false
    },
    track: {
      type: Boolean,
      default: false
    }
  },
  submitStatus: {
    nowPlaying: {
      type: Boolean,
      default: false
    },
    track: {
      type: Boolean,
      default: false
    }
  },
  player: String
});

module.exports = mongoose.model('HeosPlayedTrack', heosPlayedTrackSchema, 'heosPlayedTracks');
