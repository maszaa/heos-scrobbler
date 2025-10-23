from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="HEOS_SCROBBLER",
    settings_files=["settings.toml", ".secrets.toml"],
)
