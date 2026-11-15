"""Tests for pressure measurement history and trend calculation."""

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src"),
)

from pressure_history import (
    calculate_trend,
    load_history,
    save_measurement,
)


class PressureHistoryTests(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.path = Path(self.directory.name) / "pressure_history.json"
        self.now = datetime(
            2026, 11, 15, 18, 0, tzinfo=timezone.utc
        )

    def add_measurement(self, hours_ago, pressure):
        return save_measurement(
            self.path,
            pressure,
            self.now - timedelta(hours=hours_ago),
            now=self.now,
        )

    def test_rising_pressure(self):
        self.add_measurement(3, 1000.0)
        history = self.add_measurement(0, 1001.2)

        self.assertEqual(
            calculate_trend(history, now=self.now),
            "rising",
        )

    def test_falling_pressure(self):
        self.add_measurement(3, 1001.2)
        history = self.add_measurement(0, 1000.0)

        self.assertEqual(
            calculate_trend(history, now=self.now),
            "falling",
        )

    def test_steady_pressure(self):
        self.add_measurement(3, 1000.0)
        history = self.add_measurement(0, 1000.2)

        self.assertEqual(
            calculate_trend(history, now=self.now),
            "steady",
        )

    def test_missing_history(self):
        history = self.add_measurement(0, 1000.0)

        self.assertIsNone(
            calculate_trend(history, now=self.now)
        )

    def test_duplicate_measurement(self):
        self.add_measurement(0, 1000.0)
        self.add_measurement(0, 1000.0)

        history = load_history(self.path, now=self.now)

        self.assertEqual(len(history), 1)

    def test_old_measurement_is_rejected(self):
        self.add_measurement(25, 1000.0)

        history = load_history(self.path, now=self.now)

        self.assertEqual(history, [])

    def test_stale_current_measurement(self):
        self.add_measurement(4, 1000.0)
        history = self.add_measurement(1, 1001.0)

        self.assertIsNone(
            calculate_trend(history, now=self.now)
        )

    def test_missing_comparison_window(self):
        self.add_measurement(5, 1000.0)
        history = self.add_measurement(0, 1001.0)

        self.assertIsNone(
            calculate_trend(history, now=self.now)
        )

    def test_corrupted_history(self):
        self.path.write_text(
            "{invalid json",
            encoding="utf-8",
        )

        self.assertEqual(
            load_history(self.path, now=self.now),
            [],
        )

    def test_future_measurement_is_rejected(self):
        history = save_measurement(
            self.path,
            1000.0,
            self.now + timedelta(minutes=10),
            now=self.now,
        )

        self.assertEqual(history, [])

    def test_history_persists(self):
        self.add_measurement(3, 1000.0)
        self.add_measurement(0, 1001.0)

        history = load_history(self.path, now=self.now)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["pressure"], 1000.0)
        self.assertEqual(history[1]["pressure"], 1001.0)


if __name__ == "__main__":
    unittest.main()
