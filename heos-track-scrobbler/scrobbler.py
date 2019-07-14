import os

from flask import Flask, jsonify, make_response, request
import pylast

# 0 = disabled
SCROBBLE_MIN_LENGTH = float(os.environ.get("SCROBBLE_MIN_LENGTH", 0))
SCROBBLE_MAX_LENGTH = float(os.environ.get("SCROBBLE_MAX_LENGTH", 0))

app = Flask(__name__)

def get_last_fm_network():
  return pylast.LastFMNetwork(
    api_key=os.environ.get("LAST_FM_KEY"),
    api_secret=os.environ.get("LAST_FM_SECRET"),
    username=os.environ.get("LAST_FM_USERNAME"),
    password_hash=pylast.md5(os.environ.get("LAST_FM_PASSWORD"))
  )

def scrobbleIsValid(data):
  last_fm_network = get_last_fm_network()
  track_duration = last_fm_network.get_track(
    artist=data.get("artist"),
    title=data.get("title")
  ).get_duration()

  if track_duration:
    listening_duration = (data["finishedAt"] - data["startedAt"]) * 1000

    if SCROBBLE_MIN_LENGTH and listening_duration < SCROBBLE_MIN_LENGTH * track_duration:
      return False
    if SCROBBLE_MAX_LENGTH and listening_duration > SCROBBLE_MAX_LENGTH * track_duration:
      return False
  return True

@app.route("/scrobble", methods=["POST"])
def scrobble():
  try:
    last_fm_network = get_last_fm_network()
    data = request.json
    data["startedAt"] = int(data.get("startedAt"))
    data["finishedAt"] = int(data.get("finishedAt"))

    if (scrobbleIsValid(data) is True):
      last_fm_network.scrobble(
        artist=data.get("artist"),
        title=data.get("title"),
        timestamp=int(data.get("finishedAt")),
        album=data.get("album")
      )
      return make_response(jsonify(data), 200)

    data["invalid"] = True
    return make_response(jsonify(data), 400)
  except Exception as err:
    print(err.__class__.__name__, err)

    return make_response(
      jsonify(
        {
          "error": str(err)
        }
      ),
      500
    )

@app.route("/nowPlaying", methods=["POST"])
def now_playing():
  try:
    last_fm_network = get_last_fm_network()
    data = request.json

    last_fm_network.update_now_playing(
      artist=data.get("artist"),
      title=data.get("title"),
      album=data.get("album")
    )

    return make_response(jsonify(data), 200)
  except Exception as err:
    print(err.__class__.__name__, err)

    return make_response(
      jsonify(
        {
          "error": str(err)
        }
      ),
      500
    )
