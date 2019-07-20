const fs = require('fs');
const heos = require('heos-api');
const moment = require('moment');
const mongoose = require('mongoose');
const path = require('path');

const HeosPlayedTrack = require('../models/HeosPlayedTrack');
const HeosPlayer = require('../models/HeosPlayer');
const ListenerError = require('../models/Error.js')


class HeosTrackListener {
  static async initialize(options) {
    return new Promise((resolve, reject) => {
      heos.discoverDevices(
        {
          timeout: parseInt(process.env.HEOS_DISCOVER_DEVICES_TIMEOUT || 10000, 10)
        },
        async (address) => {
          options && options.informOnDiscovery ? console.log(`Found HEOS device with IP address ${address}`) : null;

          await HeosTrackListener.initializeConnection(address);
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

  static async initializeConnection(address) {
    const connection = await heos.connect(address)
      .catch((err) => HeosTrackListener.logError(`Error occured while connecting to HEOS device with IP address ${address}`, err));

    if (connection) {
      console.log(`Connected to HEOS device with IP address ${address}`)

      connection.write('system', 'prettify_json_response', { enable: 'on' })
        .write('system', 'register_for_change_events', { enable: 'on' })
        .on({commandGroup: 'player', command: 'get_now_playing_media'}, HeosTrackListener.handleTrack)
        .write('player', 'get_players')
        .once({commandGroup: 'player', command: 'get_players'}, HeosTrackListener.handlePlayers)
        .on({commandGroup: 'event', command: 'player_now_playing_changed'}, (data) => {
          connection.write('player', 'get_now_playing_media', { pid: HeosTrackListener.getPlayerPid(data) });
        })
        .on({commandGroup: 'event', command: 'player_now_playing_progress'}, HeosTrackListener.handleTrackDuration)
        .onClose((err) => {
          console.log(`Connection to HEOS device with ${address} closed${err ? ' by error' : ''}`);
        })
        .onError(async (err) => {
          HeosTrackListener.logError(
            `Error occured while connected to HEOS device with address ${address}`,
            err
          );

          console.log(`Reconnecting to HEOS device with address ${address}`);
          await HeosTrackListener.initializeConnection(address);
        });

      HeosTrackListener.setupDeviceHeartbeat(connection);
      HeosTrackListener.loadAdditionalConnectionModificators(connection);

      HeosTrackListener.connections[address] = connection;
    }
  }

  static setupDeviceHeartbeat(connection) {
    setInterval(
      () => {
        connection.write('system', 'heart_beat');
      },
      parseInt(process.env.HEOS_HEARTBEAT_INTERVAL || 10000, 10)
    );
  }

  static loadAdditionalConnectionModificators(connection) {
    const additionalHeosConnectionModificatorPath = path.join(__dirname, 'additional');

    fs.readdirSync(additionalHeosConnectionModificatorPath).forEach((file) => {
      if (file.split('.').pop() === 'js') {
        require(path.join(additionalHeosConnectionModificatorPath, file))(connection);
        console.log(`Loaded additional HEOS connection modificator: ${file}`);
      }
    });
  }

  static async closeConnections() {
    await Promise.all(Object.keys(HeosTrackListener.connections)
      .map((address) => {
        console.log(`Closing connection to HEOS device with address ${address}`);

        const closePromise = HeosTrackListener.connections[address].close()
          .catch((err) => HeosTrackListener.logError(`Error closing connection to HEOS device with address ${address}`, err));
        delete HeosTrackListener.connections[address];

        return closePromise;
      })
    );
  }

  static async logError(message, err, data) {
    const error = await ListenerError.create(
      {
        message: message,
        error: {
          error: err.toString(),
          file: err.fileName,
          line: err.lineNumber,
          column: err.columnNumber
        },
        info: data
      }
    )
      .catch(console.error);
    error ? console.error(`Error occured, id: `, error._id) : null;
  }

  static getPlayerPid(data) {
    return data.heos.message.split('=').pop();
  }

  static async handleTrackDuration(data) {
    try {
      const keyValues = data.heos.message.split('&');
      const pid = keyValues.shift().split('=').pop();

      if (HeosTrackListener.nowPlaying[pid] && !HeosTrackListener.nowPlaying[pid].duration) {
        HeosTrackListener.nowPlaying[pid].duration = parseInt(keyValues.pop().split('=').pop(), 10) / 1000
        await HeosTrackListener.nowPlaying[pid].save()
          .catch((err) => HeosTrackListener.logError('Error saving track', err, HeosTrackListener.nowPlaying[pid]));
      }
    } catch(err) {
      HeosTrackListener.logError("Erronous track duration", err);
    }
  }

  static async handlePlayers(data) {
    data = data.payload;

    data.map(async (player) => {
      let heosPlayer = await HeosPlayer.findOne(
        {
          address: player.ip,
          pid: player.pid
        }
      )
        .catch((err) => HeosTrackListener.logError(`Error querying player with address ${address} and pid ${pid}`, err));

      if (!heosPlayer) {
        console.log(`HEOS player with pid ${player.pid} and address ${player.ip} wasn't found at the database, adding player now, will trigger reconnect`);

        heosPlayer = await HeosPlayer.create({
          address: player.ip,
          pid: player.pid,
          info: player
        })
          .catch((err) => HeosTrackListener.logError(`Error creating player with address ${address} and pid ${pid}`, err));
      }

      HeosTrackListener.players[heosPlayer.pid] = heosPlayer;
    });
  }

  static async handleTrack(data) {
    const pid = HeosTrackListener.getPlayerPid(data);
    const now = moment().unix();
    data = data.payload;

    // HEOS device emits duplicate 'player_now_playing_changed' events when manually changing track. Prevent scrobbling those.
    const validNowPlayingChange = HeosTrackListener.nowPlaying[pid] &&
      HeosTrackListener.nowPlaying[pid].startedAt &&
      now - HeosTrackListener.nowPlaying[pid].startedAt > HeosTrackListener.players[pid].minimumTimeBetweenNowPlayingChange;

    if (validNowPlayingChange) {
      HeosTrackListener.nowPlaying[pid].finishedAt = moment().unix();
      await HeosTrackListener.nowPlaying[pid].save()
        .catch((err) => HeosTrackListener.logError('Error saving track', err, HeosTrackListener.nowPlaying[pid]));
    }

    const validNowPlayingChangeOrFirstNowPlaying = validNowPlayingChange || !HeosTrackListener.nowPlaying[pid];
    const validNowPlayingType = data.type === 'song' || !HeosTrackListener.players[pid].usbAndNetworkOnly;

    if (validNowPlayingChangeOrFirstNowPlaying && validNowPlayingType) {
      HeosTrackListener.nowPlaying[pid] = await HeosPlayedTrack.create({
        type: data.type,
        source: data.mid,
        title: data.song,
        artist: data.artist,
        album: data.album,
        imageUrl: data.image_url,
        startedAt: now,
        submit: HeosTrackListener.players[pid].submit,
        player: pid
      })
        .catch((err) => HeosTrackListener.logError('Error creating track', err, data));
    }
  }
}

HeosTrackListener.players = {};
HeosTrackListener.nowPlaying = {};
HeosTrackListener.unsubmittedTracks = {};
HeosTrackListener.connections = {};

module.exports = HeosTrackListener;
