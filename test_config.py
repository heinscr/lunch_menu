"""Offline installer configuration checks using synthetic values."""
from pathlib import Path
import tempfile
import unittest

from config import REQUIRED, load_config


class ConfigTests(unittest.TestCase):
    def settings(self):
        values = {key: "example-value" for key in REQUIRED}
        values.update(
            TRONBYT_SERVER_URL="http://localhost:8000",
            TRONBYT_PASSWORD="'example&with#symbols=inside'",
            DISPLAY_TIME_SECONDS="60",
        )
        return values

    def load(self, values):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "\n".join(f"{key}={value}" for key, value in values.items()),
                encoding="utf-8",
            )
            return load_config(path)

    def test_quotes_and_password_symbols_are_preserved(self):
        config = self.load(self.settings())
        self.assertEqual(config["TRONBYT_PASSWORD"], "example&with#symbols=inside")
        self.assertEqual(config["TRONBYT_SERVER_URL"], "http://localhost:8000")

    def test_server_url_requires_http_scheme_and_host(self):
        for url in ("ftp://server.example", "https:///missing-host", "https://user:pass@server.example"):
            with self.subTest(url=url):
                with self.assertRaisesRegex(ValueError, "TRONBYT_SERVER_URL"):
                    self.load(dict(self.settings(), TRONBYT_SERVER_URL=url))

    def test_missing_api_key_is_not_accepted(self):
        with self.assertRaisesRegex(ValueError, "TRONBYT_API_KEY"):
            self.load(dict(self.settings(), TRONBYT_API_KEY=""))

    def test_display_time_must_be_positive_integer(self):
        for duration in ("0", "-1", "20.5", "abc"):
            with self.subTest(duration=duration):
                with self.assertRaisesRegex(ValueError, "DISPLAY_TIME_SECONDS"):
                    self.load(dict(self.settings(), DISPLAY_TIME_SECONDS=duration))


if __name__ == "__main__":
    unittest.main()
