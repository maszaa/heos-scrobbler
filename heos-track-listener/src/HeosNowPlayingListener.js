const axios = require('axios');
const heos = require('heos-api');
const moment = require('moment');

const HeosTrack = require('./HeosTrack');

class HeosTrackListener {
  static async initialize() {
    const connection = await heos.connect(process.env.HEOS_DEVICE_ADDRESS);

    connection.write('system', 'prettify_json_response', { enable: 'on' })
      .write('system', 'register_for_change_events', { enable: 'on' })
      .on({commandGroup: 'player', command: 'get_now_playing_media'}, HeosTrackListener.handleTrack)
      .on({commandGroup: 'event', command: 'player_now_playing_changed'}, (data) => {
        connection.write('player', 'get_now_playing_media', { pid: data.heos.message.split('=').pop() })
      });

    axios.defaults.headers.common['Content-Type'] = 'application/json;charset=UTF-8';
    axios.defaults.headers.common['Access-Control-Allow-Origin'] = '*';
  }

  static async handleTrack(data) {
    data = data.payload;
    console.log('HEOS NOW PLAYING', data);

    const now = moment().unix();

    // HEOS device emits duplicate 'player_now_playing_changed' events when manually changing track. Prevent scrobbling those.
    if (HeosTrackListener.nowPlaying && HeosTrackListener.nowPlaying.startedAt && now - HeosTrackListener.nowPlaying.startedAt > 10) {
      await HeosTrackListener.submitTrack();
    }

    if (data.type === 'song') {
      HeosTrackListener.nowPlaying = new HeosTrack(data.song, data.artist, data.album, now);
      await HeosTrackListener.submitNowPlaying();
    }
  }

  static async submitTrack() {
    if (HeosTrackListener.nowPlaying && HeosTrackListener.nowPlaying.title && HeosTrackListener.nowPlaying.artist) {
      const finishedAt = moment().unix();
      HeosTrackListener.unsubmittedTracks[finishedAt] = HeosTrackListener.nowPlaying;
      HeosTrackListener.nowPlaying = null;

      await Promise.all(Object.keys(HeosTrackListener.unsubmittedTracks).map((key) => {
        return axios({
          method: 'POST',
          url: `${process.env.HEOS_SUBMIT_BASE_URL}/scrobble`,
          data: {
            ...HeosTrackListener.unsubmittedTracks[key],
            finishedAt: key
          }
        })
          .then((response) => {
            console.log('TRACK SUBMIT RESPONSE', response.data);
            delete HeosTrackListener.unsubmittedTracks[key];
          })
          .catch((err) => {
            console.error('TRACK SUBMIT ERROR', err.response.status, err.response.data);
          });
      }));

    }
  }

  static async submitNowPlaying() {
    if (HeosTrackListener.nowPlaying && HeosTrackListener.nowPlaying.title && HeosTrackListener.nowPlaying.artist) {
      return axios({
        method: 'POST',
        url: `${process.env.HEOS_SUBMIT_BASE_URL}/nowPlaying`,
        data: HeosTrackListener.nowPlaying,
      })
        .catch((err) => {
          console.error('NOW PLAYING SUBMIT ERROR', err.response.status, err.response.data);
        });
    }
  }
}

HeosTrackListener.nowPlaying = null;
HeosTrackListener.unsubmittedTracks = {};

module.exports = HeosTrackListener;
