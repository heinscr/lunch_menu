"""Upload and configure the Medway Lunch Menu app on Tronbyt."""
import http.cookiejar
import html
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

from config import load_config

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "tronbyt" / "lunch_schedule.star"


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, base):
        self.origin = urllib.parse.urlsplit(base)[:2]

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl)[:2] != self.origin:
            raise ValueError("Tronbyt redirected outside the configured server.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self):
        self.config = load_config()
        self.base = self.config["TRONBYT_SERVER_URL"]
        self.device = urllib.parse.quote(self.config["TRONBYT_DEVICE_ID"], safe="")
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            SameOriginRedirect(self.base),
        )
        self.opener = opener
        self.form(
            "/auth/login",
            {
                "username": self.config["TRONBYT_USERNAME"],
                "password": self.config["TRONBYT_PASSWORD"],
            },
        )

    def request(self, path, body=None, headers=None, method=None):
        request = urllib.request.Request(self.base + path, body, headers or {}, method=method)
        with self.opener.open(request, timeout=90) as response:
            if "/auth/login" in response.url:
                raise ValueError("Tronbyt login failed.")
            return response.read(), urllib.parse.urlsplit(response.url).path

    def form(self, path, fields):
        return self.request(
            path,
            urllib.parse.urlencode(fields).encode(),
            {"Content-Type": "application/x-www-form-urlencoded"},
        )

    def api(self, path, payload=None, method=None):
        body = None if payload is None else json.dumps(payload).encode()
        return self.request(
            "/v0/devices/" + self.device + path,
            body,
            {
                "Authorization": "Bearer " + self.config["TRONBYT_API_KEY"],
                "Content-Type": "application/json",
            },
            method,
        )

    def upload(self):
        boundary = "Tronbyt" + uuid.uuid4().hex
        content = APP_FILE.read_bytes()
        body = (
            (
                "--"
                + boundary
                + '\r\nContent-Disposition: form-data; name="file"; filename="lunch_schedule.star"\r\n'
                + "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
            + content
            + ("\r\n--" + boundary + "--\r\n").encode()
        )
        page, _ = self.request(
            "/devices/" + self.device + "/uploadapp",
            body,
            {"Content-Type": "multipart/form-data; boundary=" + boundary},
        )
        return page.decode()


def main():
    client = Client()
    page = client.upload()
    state = ROOT / ".local" / "installation.json"
    state.parent.mkdir(exist_ok=True)
    installations, _ = client.api("/installations")
    existing = {item["id"] for item in json.loads(installations)["installations"]}
    identity = {
        "server": client.base,
        "device": client.device,
        "user": client.config["TRONBYT_USERNAME"],
    }
    saved = json.loads(state.read_text(encoding="utf-8")) if state.exists() else {}
    installation = saved.get("installation") if saved.get("target") == identity else None
    if installation not in existing:
        matches = re.findall(r'(?:value|data-path)="([^"]*lunch_schedule[^"]*\.star)"', page)
        if not matches:
            raise ValueError(
                "Uploaded app, but could not identify its install path. "
                "Install it through the Tronbyt web UI."
            )
        _, path = client.form(
            "/devices/" + client.device + "/addapp",
            {
                "name": "Medway Lunch Menu",
                "path": html.unescape(matches[0]),
                "uinterval": "1",
                "display_time": client.config["DISPLAY_TIME_SECONDS"],
            },
        )
        match = re.search(r"/devices/[^/]+/([^/]+)/config", path)
        if not match:
            raise ValueError("App creation did not return a configuration page.")
        installation = match[1]
        state.write_text(
            json.dumps({"target": identity, "installation": installation}),
            encoding="utf-8",
        )

    display_time = client.config["DISPLAY_TIME_SECONDS"]
    client.request(
        "/devices/" + client.device + "/" + installation + "/config",
        json.dumps(
            {
                "enabled": True,
                "uinterval": 1,
                "display_time": int(display_time),
                "show_full_animation": "true",
                "config": {
                    "timezone": "US/Eastern",
                    "display_time_seconds": display_time,
                },
            }
        ).encode(),
        {"Content-Type": "application/json"},
    )
    print("Medway Lunch Menu uploaded and configured.")
    print("Check its preview in Tronbyt.")
    print("Configuration:", client.base + "/devices/" + client.device + "/" + installation + "/config")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        raise SystemExit(
            f"Tronbyt returned HTTP {error.code}. Check your server settings and account access."
        ) from None
    except OSError:
        raise SystemExit("Could not reach Tronbyt or read/write local files.") from None
    except ValueError as error:
        raise SystemExit(str(error)) from None
