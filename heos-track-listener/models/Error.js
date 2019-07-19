const mongoose = require('mongoose');
const moment = require('moment');
const Schema = mongoose.Schema;

const errorSchema = new Schema({
  source: {
    type: String,
    default: 'heos-track-listener'
  },
  message: String,
  info: Schema.Types.Mixed,
  date: {
    type: Date,
    default: moment
  }
});

module.exports = mongoose.model('Error', errorSchema, 'errors');
