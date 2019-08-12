db = db.getSiblingDB('heosScrobbler');

user = db.getUser(heosScrobblerUser);

if (!user) {
  db.createUser({
    user: heosScrobblerUser,
    pwd: heosScrobblerPassword,
    roles: [
      'readWrite'
    ]
  });
}
