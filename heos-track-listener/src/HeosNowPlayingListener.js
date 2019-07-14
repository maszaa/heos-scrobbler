const axios = require('axios');
const heos = require('heos-api');
const moment = require('moment');

const HeosTrack = require('./HeosTrack');

class HeosTrackListener {
  static async initialize() {
    heos.discoverDevices({timeout: 10000}, async (address) => {
      console.log(`Found HEOS device with IP address ${address}`);

      const connection = await heos.connect(address)
        .catch((err) => {
          console.error(`Following error occured while connecting to HEOS device with IP address ${address}:`, err);
        });

      if (!connection.closed) {
        console.log(`Connected to HEOS device with IP adress ${address}`)

        connection.write('system', 'prettify_json_response', { enable: 'on' })
          .write('system', 'register_for_change_events', { enable: 'on' })
          .on({commandGroup: 'player', command: 'get_now_playing_media'}, HeosTrackListener.handleTrack)
          .on({commandGroup: 'player', command: 'get_player_info'}, HeosTrackListener.handlePlayerInfo)
          .on({commandGroup: 'event', command: 'player_now_playing_changed'}, (data) => {
            const pid = HeosTrackListener.getPlayerPid(data);
            connection.write('player', 'get_player_info', { pid: pid })
              .write('player', 'get_now_playing_media', { pid: pid });
          });
      }
    })

    axios.defaults.headers.common['Content-Type'] = 'application/json;charset=UTF-8';
    axios.defaults.headers.common['Access-Control-Allow-Origin'] = '*';
  }

  static getPlayerPid(data) {
    return data.heos.message.split('=').pop();
  }

  static handlePlayerInfo(data) {
    HeosTrackListener.playerName = data.payload.name;
  }

  static async handleTrack(data) {
    const pid = HeosTrackListener.getPlayerPid(data);

    data = data.payload;
    console.log(`${HeosTrackListener.playerName || 'HEOS DEVICE'} IS NOW PLAYING`, data);

    const now = moment().unix();

    // HEOS device emits duplicate 'player_now_playing_changed' events when manually changing track. Prevent scrobbling those.
    if (HeosTrackListener.nowPlaying[pid] &&
        HeosTrackListener.nowPlaying[pid].startedAt &&
        now - HeosTrackListener.nowPlaying[pid].startedAt > 10) {
      await HeosTrackListener.submitTrack(pid);
    }

    if (data.type === 'song' || !process.env.SUBMIT_ONLY_USB_AND_NETWORK) {
      HeosTrackListener.nowPlaying[pid] = new HeosTrack(data.song, data.artist, data.album, now);
      await HeosTrackListener.submitNowPlaying(pid);
    }
  }

  static async submitTrack(pid) {
    if (HeosTrackListener.nowPlaying[pid] &&
        HeosTrackListener.nowPlaying[pid].title &&
        HeosTrackListener.nowPlaying[pid].artist) {
      const finishedAt = moment().unix();

      HeosTrackListener.unsubmittedTracks[pid][finishedAt] = HeosTrackListener.nowPlaying[pid];
      HeosTrackListener.nowPlaying[pid] = null;

      await Promise.all(Object.keys(HeosTrackListener.unsubmittedTracks)
        .map((pid) => {
          Object.keys(HeosTrackListener.unsubmittedTracks[pid])
            .map((finishedAt) => {
              return axios({
                method: 'POST',
                url: `${process.env.HEOS_SUBMIT_BASE_URL}/scrobble`,
                data: {
                  ...HeosTrackListener.unsubmittedTracks[pid][finishedAt],
                  finishedAt: finishedAt
                }
              })
                .then((response) => {
                  console.log('TRACK SUBMIT RESPONSE', response.data);
                  delete HeosTrackListener.unsubmittedTracks[pid][key];
                })
                .catch((err) => {
                  if (err.response) {
                    console.error('TRACK SUBMIT ERROR', err.response.status, err.response.data);
                  } else {
                    console.error('TRACK SUBMIT ERROR', err);
                  }
                });
            })
        })
      );

    }
  }

  static async submitNowPlaying(pid) {
    if (HeosTrackListener.nowPlaying[pid] &&
        HeosTrackListener.nowPlaying[pid].title &&
        HeosTrackListener.nowPlaying[pid].artist) {
      return axios({
        method: 'POST',
        url: `${process.env.HEOS_SUBMIT_BASE_URL}/nowPlaying`,
        data: HeosTrackListener.nowPlaying[pid],
      })
        .catch((err) => {
          console.error('NOW PLAYING SUBMIT ERROR', err.response.status, err.response.data);
        });
    }
  }
}

HeosTrackListener.playerName = null;
HeosTrackListener.nowPlaying = {};
HeosTrackListener.unsubmittedTracks = {};

module.exports = HeosTrackListener;
