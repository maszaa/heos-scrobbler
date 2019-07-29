const mongoose = require('mongoose');

const HeosNowPlayingListener = require('./heos/HeosNowPlayingListener');
const HeosPlayer = require('./models/HeosPlayer');

async function initialize() {
  await mongoose.connect(
    `mongodb://${process.env.MONGO_USER}:${process.env.MONGO_PASSWORD}@${process.env.MONGO_HOST}:${process.env.MONGO_PORT}/${process.env.MONGO_DB}`,
    {
      useNewUrlParser: true,
      useFindAndModify: false
    }
  );

  const heosNowPlayingListener = new HeosNowPlayingListener();

  await heosNowPlayingListener.initialize()
    .catch((err) => {
      console.error(err);
      process.exit(1);
    });
}

module.exports = initialize();
