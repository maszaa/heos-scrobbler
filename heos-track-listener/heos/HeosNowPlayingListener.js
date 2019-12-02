const fs = require('fs');
const heos = require('heos-api');
const moment = require('moment');
const mongoose = require('mongoose');
const path = require('path');

const sleep = require('util').promisify(setTimeout);

const HeosPlayedTrack = require('../models/HeosPlayedTrack');
const HeosPlayer = require('../models/HeosPlayer');
const ListenerError = require('../models/Error.js')


class HeosTrackListener {
  constructor() {
    this.nowPlaying = {};
    this.reconnectingToAddresses = [];

    this.handlePlayers = this.handlePlayers.bind(this);
    this.handleTrack = this.handleTrack.bind(this);
    this.handleTrackDuration = this.handleTrackDuration.bind(this);
    this.handleConnectionError = this.handleConnectionError.bind(this)
  }

  async initialize() {
    return new Promise((resolve, reject) => {
      const connections = {};

      heos.discoverDevices(
        {
          timeout: parseInt(process.env.HEOS_DISCOVER_DEVICES_TIMEOUT || 10000, 10) // ms
        },
        async (address) => {
          console.log(`Found HEOS device with IP address ${address}`);

          connections[address] = await this.initializeConnection(address);
        },
        (addresses) => {
          console.log(`HEOS discover devices timeout reached, found ${addresses.length} devices`);

          if (!addresses.length) {
            reject(new Error('Please add HEOS devices to your network, turn them on or connect your PC to network which has them connected'));
          }

          resolve(connections);
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
        .onClose((err) => {
          const message = `Connection to HEOS device with ${address} closed${err ? ' by error' : ''}`;
        })
        .onError(async (err) => await this.handleConnectionError(
          connection,
          address,
          `Error occured while connected to HEOS device with address ${address}`,
          err)
        );

      this.setupDeviceHeartbeat(connection, address);
      this.loadAdditionalConnectionModificators(connection);
    }

    return connection;
  }

  setupDeviceHeartbeat(connection, address) {
    connection.on({commandGroup: 'system', command: 'heart_beat'}, (data) => {
      if (data.heos.result !== 'success') {
        connection.heartbeatSuccessful = false;
      } else {
        connection.heartbeatSuccessful = true;
      }
    });

    const heartbeat = setInterval(
      async () => {
        if (connection.hasOwnProperty('heartbeatSuccessful') && !connection.heartbeatSuccessful && !connection.closed) {
          await this.handleConnectionError(connection, address, `Timeout or error occured while connected to HEOS device with address ${address}`)
        } else if (!connection.closed) {
          connection.heartbeatSuccessful = false;
          connection.write('system', 'heart_beat');
          return;
        }

        clearInterval(heartbeat);
      },
      parseInt(process.env.HEOS_HEARTBEAT_INTERVAL || 10000, 10) // ms
    );
  }

  loadAdditionalConnectionModificators(connection) {
    const additionalHeosConnectionModificatorPath = path.join(__dirname, 'additional');

    fs.readdirSync(additionalHeosConnectionModificatorPath).forEach((file) => {
      if (file.split('.').pop() === 'js') {
        require(path.join(additionalHeosConnectionModificatorPath, file))(connection, this);
        console.log(`Loaded additional HEOS connection modificator: ${file}`);
      }
    });
  }

  async handleConnectionError(connection, address, message, err) {
    this.logError(message, err);

    if (!connection.closed) {
      console.log(`Closing connection to HEOS device with address ${address}`);

      await connection.close()
        .catch((err) => this.logError(`Error closing connection to HEOS device with address ${address}`, err));
    }

    if (!this.reconnectingToAddresses.includes(address)) {
      await this.reconnect(address);
    }
  }

  async reconnect(address) {
    this.reconnectingToAddresses.push(address);

    let connection;
    const retryOptions = {
      retry: 1,
      interval: parseInt(process.env.HEOS_RECONNECT_INTERVAL || 30000, 10), // ms
      maxCount: parseInt(process.env.HEOS_RECONNECT_RETRIES || 0, 10) // 0 = disabled
    };

    console.log(`Reconnecting to HEOS device with address ${address}`);

    while (!connection && (!retryOptions.maxCount || retryOptions.maxCount && retryOptions.retry <= retryOptions.maxCount)) {
      if (retryOptions.retry - 1) {
        console.log(`Reconnect to ${address} unsuccessful, waiting ${retryOptions.interval / 1000} seconds before next attempt`);
        await sleep(retryOptions.interval);
        console.log(`Attempt ${retryOptions.retry} to reconnect to ${address}, ${retryOptions.maxCount ? `${retryOptions.maxCount - retryOptions.retry} attempts left` : 'unlimited retries'}`);
      }

      connection = await this.initializeConnection(address);
      ++retryOptions.retry;
    }

    this.reconnectingToAddresses = this.reconnectingToAddresses.filter((reconnectingToAddress) => reconnectingToAddress !== address);
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
            undefined
        ),
        info: data
      }
    )
      .catch(console.error);
    error && console.error(`${error.message}${error.error ? ` - ${error.error.error}` : ''}, id: ${error._id}`);
  }

  getPlayerPid(data) {
    const message = data.heos.message.includes('&') ? data.heos.message.split('&').shift() : data.heos.message
    return message.split('=').pop();
  }

  async handleTrackDuration(data) {
    const pid = this.getPlayerPid(data);

    if (this.nowPlaying[pid]) {
      const nowPlaying = await HeosPlayedTrack.findOne({
        _id: this.nowPlaying[pid],
        duration: {
          $exists: false
        },
        'ready.nowPlaying': false
      })
        .catch((err) => this.logError(`Error querying track with id ${this.nowPlaying[pid]}`, err));

      if (nowPlaying) {
        nowPlaying.duration = parseInt(data.heos.message.split('&').pop().split('=').pop(), 10) / 1000;
        nowPlaying.ready.nowPlaying = true;

        await nowPlaying.save()
          .catch((err) => this.logError(`Error updating duration for track ${nowPlaying._id}`, err, nowPlaying));
      }
    }
  }

  async handlePlayers(data) {
    data = data.payload;

    await Promise.all(data.map((player) => {
      return HeosPlayer.findOneAndUpdate(
        {
          address: player.ip,
          pid: player.pid
        },
        {
          address: player.ip,
          pid: player.pid,
          info: player
        },
        {
          upsert: true,
          setDefaultsOnInsert: true
        }
      )
        .catch((err) => this.logError(`Error creating player with address ${address} and pid ${pid}`, err));
    }));
  }

  async handleTrack(data) {
    const pid = this.getPlayerPid(data);
    const now = moment().unix();
    data = data.payload;

    if (this.nowPlaying[pid]) {
      await HeosPlayedTrack.updateOne(
        {
          _id: this.nowPlaying[pid],
          startedAt: {
            $exists: true
          },
          'ready.nowPlaying': true,
          'ready.track': false
        },
        {
          finishedAt: now,
          'ready.track': true
        }
      )
        .catch((err) => this.logError(`Error updating track with id ${this.nowPlaying[pid]}`, err));
    }

    const player = await HeosPlayer.findOne({
      pid: pid
    })
      .catch((err) => this.logError(`Error querying player with pid ${pid}`, err))

    if (data.type === 'song' || (player && !player.usbAndNetworkOnly)) {
      const nowPlaying = await HeosPlayedTrack.create({
        type: data.type,
        source: data.mid,
        title: data.song,
        artist: data.artist,
        album: data.album,
        imageUrl: data.image_url,
        startedAt: now,
        submit: player ? player.submit : undefined,
        player: pid
      })
        .catch((err) => this.logError('Error creating track', err, data));

      this.nowPlaying[pid] = nowPlaying._id;
    }
  }
}

module.exports = HeosTrackListener;
