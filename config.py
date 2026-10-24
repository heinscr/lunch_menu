"""Load local Tronbyt installer settings without external dependencies."""
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
REQUIRED = (
    "TRONBYT_SERVER_URL",
    "TRONBYT_DEVICE_ID",
    "TRONBYT_USERNAME",
    "TRONBYT_PASSWORD",
    "TRONBYT_API_KEY",
    "DISPLAY_TIME_SECONDS",
)


def load_config(path=None):
    path = Path(path) if path else ROOT / ".env"
    if not path.exists():
        raise ValueError("Copy .env.example to .env and fill in your Tronbyt settings first.")
    config = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise ValueError("Invalid .env line; expected KEY=value.")
        value = value.strip()
        if value[:1] in ("'", '"'):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError("Unclosed quote in .env.")
            value = value[1:-1]
        config[key.strip()] = value
    for key in REQUIRED:
        if not config.get(key):
            raise ValueError(f"Set {key} in .env first.")

    parsed = urlsplit(config["TRONBYT_SERVER_URL"])
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("TRONBYT_SERVER_URL must be an HTTP(S) base URL without credentials, query, or fragment.")

    duration = config["DISPLAY_TIME_SECONDS"]
    if not duration.isascii() or not duration.isdecimal() or int(duration) < 1:
        raise ValueError("DISPLAY_TIME_SECONDS must be a positive whole number.")
    config["TRONBYT_SERVER_URL"] = config["TRONBYT_SERVER_URL"].rstrip("/")
    return config
