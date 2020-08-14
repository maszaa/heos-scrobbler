# HEOS scrobbler

Update now playing and scrobble tracks listened with HEOS device to Last.fm. Tracks to be scrobbled must have artist and title in metadata.

Requirements: Docker, Docker-Compose, Last.fm account & API account (create later here: https://www.last.fm/api/account/create)

1. Create `.env` files in subdirectories based on `example.env` files.
2. `./start.sh`
3. After the stack has started, visit `<YOUR_MONGO_EXPRESS_HOST>:<YOUR_MONGO_EXPRESS_PORT>` using the username and password you've set and at `heosScrobbler.heosPlayers` setup players and their configuration you want to use for scrobbling. You do not need to restart the stack.
4. Same address, at `heosScrobbler.lastFmUsers` select the pre-populated user, input your Last.fm username and password and save. `heos-track-scrobbler` will generate a Last.fm session key for your account and delete the password from the database next time it attempts to scrobble (i.e. you've listened a track with your HEOS device). When you change your Last.fm user configuration you don't have to restart the stack

You can create custom event handlers and listeners for HEOS connections at `heos-track-listener/heos/additional`. Files ending with `.js` will be loaded during startup. Your handlers and listeners must take the HEOS connetion and optionally now playing listener as parameters. Take a look at the `example.js.txt` at that path.

You can define track sources to be ignored by inserting substrings of sources to `ignoreSources` array of a player document. Substrings are case insensitive. If the source (case insensitive) of the new track contains any of the defined substrings it will not be saved (i.e. scrobbled).
