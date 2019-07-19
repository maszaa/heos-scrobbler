# HEOS scrobbler

Update now playing and scrobble tracks listened with HEOS device to Last.fm. Tracks to be scrobbled must have artist and title in metadata.

Requirements: Docker, Docker-Compose, Last.fm account & API account (create later here: https://www.last.fm/api/account/create)

1. Create `.env` files in subdirectories based on `example.env` files.
2. `./start.sh`
3. After the stack has started, visit `<YOUR_MONGO_EXPRESS_HOST>:<YOUR_MONGO_EXPRESS_PORT>` using the username and password you've set and at `heosScrobbler.heosPlayers` setup players and their configuration you want to use for scrobbling. After saving your modifications the `heos-track-listener` will reconnect to HEOS devices to reload the configuration.
4. Same address, at `heosScrobbler.lastFmUsers` select the pre-populated user, input your Last.fm username and password and save. `heos-track-scrobbler` will reload and generate a Last.fm session key for your account and delete the password from the database. Every time you change your Last.fm user configuration the `heos-track-scrobbler` will reinitialize scrobbling.

You can create custom event handlers and listeners for HEOS connections at `heos-track-listener/heos/additional`. Files ending with `.js` will be loaded during startup. Your handlers and listeners must take the HEOS connetion as a parameter. Take a look at the `example.js.txt` at that path.
