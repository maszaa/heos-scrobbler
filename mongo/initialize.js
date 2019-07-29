db = db.getSiblingDB('heosScrobbler');

db.createUser({
  user: heosScrobblerUser,
  pwd: heosScrobblerPassword,
  roles: [
    'readWrite'
  ]
});

db.createCollection('heosPlayedTracks');
db.createCollection('lastFmUsers');
