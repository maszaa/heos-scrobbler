const mongoose = require('mongoose');

const HeosNowPlayingListener = require('./heos/HeosNowPlayingListener');
const HeosPlayer = require('./models/HeosPlayer');

mongoose.connect(
  `mongodb://${process.env.MONGO_USER}:${process.env.MONGO_PASSWORD}@${process.env.MONGO_HOST}:${process.env.MONGO_PORT}/${process.env.MONGO_DB}`,
  {
    useNewUrlParser: true
  }
);

HeosNowPlayingListener.initialize({informOnDiscovery: true})
  .then(() => {
    HeosPlayer.watch()
      .on('change', async () => {
        console.log('Noticed changes in HEOS player configuration, reconnecting');
        await HeosNowPlayingListener.closeConnections();
        await HeosNowPlayingListener.initialize();
      });
  })
