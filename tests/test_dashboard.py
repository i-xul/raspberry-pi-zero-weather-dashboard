import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# The application loads local configuration during import.
# Supply example configuration values for isolated tests.
with patch("dashboard_config.load_config", return_value={
    "cosy_baro_url": "http://192.0.2.10:8765/api/cosy-baro",
    "dht22_url": "https://sensor.example.com/api/lab_temp",
    "dht22_cache_path": "/tmp/dht22-test.json",
    "waveshare_lib_path": "/tmp/waveshare",
}):
    import epaper_dashboard as dashboard


class CosyBaroStatusTests(unittest.TestCase):

    def test_recent_measurement_is_online(self):
        cosy = {
            "updated": datetime.now(timezone.utc)
            - timedelta(minutes=5)
        }
        self.assertEqual(
            dashboard.cosy_baro_status(cosy, True),
            "ONLINE",
        )

    def test_old_measurement_is_stale(self):
        cosy = {
            "updated": datetime.now(timezone.utc)
            - timedelta(minutes=20)
        }
        self.assertEqual(
            dashboard.cosy_baro_status(cosy, True),
            "STALE",
        )

    def test_failed_api_is_offline(self):
        self.assertEqual(
            dashboard.cosy_baro_status(None, False),
            "OFFLINE",
        )

    def test_future_measurement_is_stale(self):
        cosy = {
            "updated": datetime.now(timezone.utc)
            + timedelta(minutes=10)
        }
        self.assertEqual(
            dashboard.cosy_baro_status(cosy, True),
            "STALE",
        )

    def test_timestamp_without_timezone_is_stale(self):
        cosy = {"updated": datetime.now()}
        self.assertEqual(
            dashboard.cosy_baro_status(cosy, True),
            "STALE",
        )


class DHT22CacheTests(unittest.TestCase):

    def test_missing_cache_returns_none(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"

            with patch.object(dashboard, "DHT22_STATE_FILE", path):
                self.assertIsNone(dashboard.load_last_good())

    def test_valid_cache_is_loaded(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"

            data = {
                "temperature": 22.5,
                "humidity": 45.0,
                "updated": datetime.now(timezone.utc).isoformat(),
            }

            with patch.object(dashboard, "DHT22_STATE_FILE", path):
                dashboard.save_last_good(data)
                self.assertEqual(dashboard.load_last_good(), data)

    def test_invalid_json_returns_none(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            path.write_text("{invalid json", encoding="utf-8")

            with patch.object(dashboard, "DHT22_STATE_FILE", path):
                self.assertIsNone(dashboard.load_last_good())


class DHT22CacheExpiryTests(unittest.TestCase):

    def check_cache(self, data):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            path.write_text(
                __import__("json").dumps(data),
                encoding="utf-8",
            )

            with patch.object(dashboard, "DHT22_STATE_FILE", path):
                return dashboard.load_last_good()

    def valid_data(self, updated):
        return {
            "temperature": 22.5,
            "humidity": 45.0,
            "updated": updated.isoformat(),
        }

    def test_cache_23_hours_old_is_valid(self):
        updated = datetime.now(timezone.utc) - timedelta(hours=23)
        self.assertIsNotNone(
            self.check_cache(self.valid_data(updated))
        )

    def test_cache_25_hours_old_is_rejected(self):
        updated = datetime.now(timezone.utc) - timedelta(hours=25)
        self.assertIsNone(
            self.check_cache(self.valid_data(updated))
        )

    def test_future_timestamp_is_rejected(self):
        updated = datetime.now(timezone.utc) + timedelta(hours=1)
        self.assertIsNone(
            self.check_cache(self.valid_data(updated))
        )

    def test_invalid_humidity_is_rejected(self):
        data = self.valid_data(datetime.now(timezone.utc))
        data["humidity"] = 150
        self.assertIsNone(self.check_cache(data))

    def test_non_numeric_temperature_is_rejected(self):
        data = self.valid_data(datetime.now(timezone.utc))
        data["temperature"] = "invalid"
        self.assertIsNone(self.check_cache(data))


class DHT22FallbackTests(unittest.TestCase):

    def test_failed_api_uses_recent_cache(self):
        cached = {
            "temperature": 22.5,
            "humidity": 45.0,
            "updated": datetime.now(timezone.utc).isoformat(),
        }

        with patch.object(dashboard, "load_last_good", return_value=cached):
            with patch.object(
                dashboard.requests,
                "get",
                side_effect=dashboard.requests.ConnectionError("Test failure"),
            ):
                data, api_ok = dashboard.fetch_dht22()

        self.assertFalse(api_ok)
        self.assertEqual(data, cached)

    def test_failed_api_without_valid_cache_is_offline(self):
        with patch.object(dashboard, "load_last_good", return_value=None):
            with patch.object(
                dashboard.requests,
                "get",
                side_effect=dashboard.requests.ConnectionError("Test failure"),
            ):
                data, api_ok = dashboard.fetch_dht22()

        self.assertFalse(api_ok)
        self.assertIsNone(data)


if __name__ == "__main__":
    unittest.main()
