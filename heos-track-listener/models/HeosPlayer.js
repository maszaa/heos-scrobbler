const mongoose = require("mongoose");
const Schema = mongoose.Schema;

const heosPlayerSchema = new Schema({
  address: String,
  pid: String,
  ignoreSources: [String],
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
  info: Object,
});

module.exports = mongoose.model("HeosPlayer", heosPlayerSchema, "heosPlayers");
