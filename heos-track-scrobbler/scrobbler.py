import os

from flask import Flask, jsonify, make_response, request
import pylast

app = Flask(__name__)

def get_last_fm_network():
  return pylast.LastFMNetwork(
    api_key=os.environ.get("LAST_FM_KEY"),
    api_secret=os.environ.get("LAST_FM_SECRET"),
    username=os.environ.get("LAST_FM_USERNAME"),
    password_hash=pylast.md5(os.environ.get("LAST_FM_PASSWORD"))
  )

@app.route("/scrobble", methods=["POST"])
def scrobble():
  try:
    last_fm_network = get_last_fm_network()
    data = request.json

    last_fm_network.scrobble(
      artist=data.get("artist"),
      title=data.get("title"),
      timestamp=int(data.get("finishedAt")),
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
