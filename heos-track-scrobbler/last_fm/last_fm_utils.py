import os

import pylast

from models.last_fm_user import LastFmUser

def get_last_fm_network(session_key=None):
  if session_key:
    return pylast.LastFMNetwork(
      api_key=os.environ.get("LAST_FM_KEY"),
      api_secret=os.environ.get("LAST_FM_SECRET"),
      session_key=session_key
    )

  return pylast.LastFMNetwork(
    api_key=os.environ.get("LAST_FM_KEY"),
    api_secret=os.environ.get("LAST_FM_SECRET")
  )


def set_last_fm_session_key(username, password):
  last_fm_network = get_last_fm_network()

  session_key = pylast.SessionKeyGenerator(last_fm_network).get_session_key(username, pylast.md5(password))

  last_fm_user = LastFmUser.objects(
    username=username,
    password=password
  ).first()

  if last_fm_user:
    last_fm_user.sessionKey = session_key
    last_fm_user.password = None
    last_fm_user.save()
    return last_fm_user
