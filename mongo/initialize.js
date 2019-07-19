db = db.getSiblingDB('heosScrobbler');

db.createUser({
  user: heosScrobblerUser,
  pwd: heosScrobblerPassword,
  roles: [
    'readWrite'
  ]
});

db.createCollection('heosPlayers');
db.createCollection('heosPlayedTracks');
db.createCollection('lastFmUsers');
