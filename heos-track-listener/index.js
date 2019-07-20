const mongoose = require('mongoose');

const HeosNowPlayingListener = require('./heos/HeosNowPlayingListener');
const HeosPlayer = require('./models/HeosPlayer');

mongoose.connect(
  `mongodb://${process.env.MONGO_USER}:${process.env.MONGO_PASSWORD}@${process.env.MONGO_HOST}:${process.env.MONGO_PORT}/${process.env.MONGO_DB}`,
  {
    useNewUrlParser: true
  }
);

const heosNowPlayingListener = new HeosNowPlayingListener();

heosNowPlayingListener.initialize({informOnDiscovery: true})
  .then(() => {
    HeosPlayer.watch()
      .on('change', async () => {
        console.log('Noticed changes in HEOS player configuration, reconnecting');
        await heosNowPlayingListener.closeConnections();
        await heosNowPlayingListener.initialize();
      });
  })
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
