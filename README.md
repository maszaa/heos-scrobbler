# HEOS Scrobbler

Update now playing and scrobble tracks listened with HEOS device to Last.fm.
Tracks to be scrobbled must have artist and title in metadata.

## Requirements:

* HEOS device
* Python 3 (3.13 and 3.14 tested)
* [uv](https://docs.astral.sh/uv/) for Python dependency management
* Last.fm account
* [Last.fm API account](https://www.last.fm/api/account/create)

## Installation

In project folder

1. `cp .secrets.toml.example .secrets.toml`
2. Fill your Last.fm details to `.secrets.toml`
3. `uv sync`

The last command will create a virtualenv `.venv` and install required Python dependencies in that.

### Additional configuration

If you wish to alter default configuration, you can do it via environment variables.
Use `HEOS_SCROBBLER_` prefix. For example:

```
export HEOS_SCROBBLER_DEBUG=true
export HEOS_SCROBBLER_RETRY_SCROBBLE_FOR_HOURS=24
```

See [Dynaconf documentation](https://www.dynaconf.com/envvars/) for more examples.

## Running

In project folder

`uv run main.py`

## Old implementation

If you need to access the old implementation, it's available in [legacy](https://github.com/maszaa/heos-scrobbler/tree/legacy) branch.
