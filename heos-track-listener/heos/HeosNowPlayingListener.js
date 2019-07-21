const fs = require('fs');
const heos = require('heos-api');
const moment = require('moment');
const mongoose = require('mongoose');
const path = require('path');

const HeosPlayedTrack = require('../models/HeosPlayedTrack');
const HeosPlayer = require('../models/HeosPlayer');
const ListenerError = require('../models/Error.js')


class HeosTrackListener {
  constructor() {
    this.players = {};
    this.nowPlaying = {};
    this.connections = {};

    this.handlePlayers = this.handlePlayers.bind(this);
    this.handleTrack = this.handleTrack.bind(this);
    this.handleTrackDuration = this.handleTrackDuration.bind(this);
    this.handleConnectionError = this.handleConnectionError.bind(this)
  }

  async initialize(options) {
    return new Promise((resolve, reject) => {
      heos.discoverDevices(
        {
          timeout: parseInt(process.env.HEOS_DISCOVER_DEVICES_TIMEOUT || 10000, 10)
        },
        async (address) => {
          options && options.informOnDiscovery ? console.log(`Found HEOS device with IP address ${address}`) : null;

          await this.initializeConnection(address);
        },
        (addresses) => {
          console.log(`HEOS discover devices timeout reached, found ${addresses.length} devices`);

          if (!addresses.length) {
            reject(new Error('Please add HEOS devices to your network, turn them on or connect your PC to network which has them connected'));
          }

          resolve(addresses);
        }
      );
    });
  }

  async initializeConnection(address) {
    const connection = await heos.connect(address)
      .catch((err) => this.logError(`Error occured while connecting to HEOS device with IP address ${address}`, err));

    if (connection) {
      console.log(`Connected to HEOS device with IP address ${address}`)

      connection.write('system', 'prettify_json_response', { enable: 'on' })
        .write('system', 'register_for_change_events', { enable: 'on' })
        .on({commandGroup: 'player', command: 'get_now_playing_media'}, this.handleTrack)
        .write('player', 'get_players')
        .once({commandGroup: 'player', command: 'get_players'}, this.handlePlayers)
        .on({commandGroup: 'event', command: 'player_now_playing_changed'}, (data) => {
          connection.write('player', 'get_now_playing_media', { pid: this.getPlayerPid(data) });
        })
        .on({commandGroup: 'event', command: 'player_now_playing_progress'}, this.handleTrackDuration)
        .onClose(async (err) => {
          const message = `Connection to HEOS device with ${address} closed${err ? ' by error' : ''}`;

          if (err) {
            await this.handleConnectionError(connection, address, message);
          } else {
            console.log(message);
          }
        })
        .onError(async (err) => await this.handleConnectionError(
          connection,
          address,
          `Error occured while connected to HEOS device with address ${address}`,
          err)
        );

      this.setupDeviceHeartbeat(connection, address);
      this.loadAdditionalConnectionModificators(connection);

      this.connections[address] = connection;
    }
  }

  setupDeviceHeartbeat(connection, address) {
    connection.heartbeatSuccessful = true;

    connection.on({commandGroup: 'system', command: 'heart_beat'}, (data) => {
      if (data.heos.result !== 'success') {
        connection.heartbeatSuccessful = false;
      } else {
        connection.heartbeatSuccessful = true;
      }
    });

    const heartbeat = setInterval(
      async () => {
        if (!connection.heartbeatSuccessful) {
          clearInterval(heartbeat);
          await this.handleConnectionError(connection, address, `Timeout or error occured while connected to HEOS device with address ${address}`)
        } else {
          connection.heartbeatSuccessful = false;
          connection.write('system', 'heart_beat');
        }
      },
      parseInt(process.env.HEOS_HEARTBEAT_INTERVAL || 10000, 10)
    );
  }

  loadAdditionalConnectionModificators(connection) {
    const additionalHeosConnectionModificatorPath = path.join(__dirname, 'additional');

    fs.readdirSync(additionalHeosConnectionModificatorPath).forEach((file) => {
      if (file.split('.').pop() === 'js') {
        require(path.join(additionalHeosConnectionModificatorPath, file))(connection);
        console.log(`Loaded additional HEOS connection modificator: ${file}`);
      }
    });
  }

  async closeConnections() {
    await Promise.all(Object.keys(this.connections)
      .map((address) => {
        console.log(`Closing connection to HEOS device with address ${address}`);

        const closePromise = this.connections[address].close()
          .catch((err) => this.logError(`Error closing connection to HEOS device with address ${address}`, err));
        delete this.connections[address];

        return closePromise;
      })
    );
  }

  async handleConnectionError(connection, address, message, err) {
    this.logError(message, err);

    if (!connection.closed) {
      console.log(`Closing connection to HEOS device with address ${address}`);

      await connection.close()
        .catch((err) => this.logError(`Error closing connection to HEOS device with address ${address}`, err));
    }

    console.log(`Reconnecting to HEOS device with address ${address}`);
    await this.initializeConnection(address);
  }

  async logError(message, err, data) {
    const error = await ListenerError.create(
      {
        message: message,
        error: (
          err ?
            {
              error: err.toString(),
              file: err.fileName,
              line: err.lineNumber,
              column: err.columnNumber
            } :
            null
        ),
        info: data
      }
    )
      .catch(console.error);
    error ? console.error(`Error occured, id: `, error._id) : null;
  }

  getPlayerPid(data) {
    return data.heos.message.split('=').pop();
  }

  async handleTrackDuration(data) {
    try {
      const keyValues = data.heos.message.split('&');
      const pid = keyValues.shift().split('=').pop();

      if (this.nowPlaying[pid] && !this.nowPlaying[pid].duration) {
        this.nowPlaying[pid].duration = parseInt(keyValues.pop().split('=').pop(), 10) / 1000
        await this.nowPlaying[pid].save()
          .catch((err) => this.logError('Error saving track', err, this.nowPlaying[pid]));
      }
    } catch(err) {
      this.logError("Erronous track duration", err);
    }
  }

  async handlePlayers(data) {
    data = data.payload;

    data.map(async (player) => {
      let heosPlayer = await HeosPlayer.findOne(
        {
          address: player.ip,
          pid: player.pid
        }
      )
        .catch((err) => this.logError(`Error querying player with address ${address} and pid ${pid}`, err));

      if (!heosPlayer) {
        console.log(`HEOS player with pid ${player.pid} and address ${player.ip} wasn't found at the database, adding player now, will trigger reconnect`);

        heosPlayer = await HeosPlayer.create({
          address: player.ip,
          pid: player.pid,
          info: player
        })
          .catch((err) => this.logError(`Error creating player with address ${address} and pid ${pid}`, err));
      }

      this.players[heosPlayer.pid] = heosPlayer;
    });
  }

  async handleTrack(data) {
    const pid = this.getPlayerPid(data);
    const now = moment().unix();
    data = data.payload;

    // HEOS device emits duplicate 'player_now_playing_changed' events when manually changing track. Prevent scrobbling those.
    const validNowPlayingChange = this.nowPlaying[pid] &&
      this.nowPlaying[pid].startedAt &&
      now - this.nowPlaying[pid].startedAt > this.players[pid].minimumTimeBetweenNowPlayingChange;

    if (validNowPlayingChange) {
      this.nowPlaying[pid].finishedAt = moment().unix();
      await this.nowPlaying[pid].save()
        .catch((err) => this.logError('Error saving track', err, this.nowPlaying[pid]));
    }

    const validNowPlayingChangeOrFirstNowPlaying = validNowPlayingChange || !this.nowPlaying[pid];
    const validNowPlayingType = data.type === 'song' || !this.players[pid].usbAndNetworkOnly;

    if (validNowPlayingChangeOrFirstNowPlaying && validNowPlayingType) {
      this.nowPlaying[pid] = await HeosPlayedTrack.create({
        type: data.type,
        source: data.mid,
        title: data.song,
        artist: data.artist,
        album: data.album,
        imageUrl: data.image_url,
        startedAt: now,
        submit: this.players[pid].submit,
        player: pid
      })
        .catch((err) => this.logError('Error creating track', err, data));
    }
  }
}

module.exports = HeosTrackListener;
