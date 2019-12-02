const mongoose = require('mongoose');

const HeosNowPlayingListener = require('./heos/HeosNowPlayingListener');
const HeosPlayer = require('./models/HeosPlayer');

async function handleSignals(signal, connections) {
  console.log(`Received ${signal}, closing connections to HEOS devices`);

  await Promise.all(Object.keys(connections)
    .map((key) => connections[key].close()
      .catch(console.error))
  )
    .catch(console.error);

  console.log('Closed HEOS connections');
  process.exit(0);
}

async function initialize() {
  await mongoose.connect(
    `mongodb://${process.env.MONGO_USER}:${process.env.MONGO_PASSWORD}@${process.env.MONGO_HOST}:${process.env.MONGO_PORT}/${process.env.MONGO_DB}`,
    {
      useNewUrlParser: true,
      useFindAndModify: false,
      useUnifiedTopology: true
    }
  );

  const heosNowPlayingListener = new HeosNowPlayingListener();

  const connections = await heosNowPlayingListener.initialize()
    .catch((err) => {
      console.error(err);
      process.exit(1);
    });

  process.on('SIGTERM', (signal) => handleSignals(signal, connections));
  process.on('SIGINT', (signal) => handleSignals(signal, connections));
}

module.exports = initialize();
