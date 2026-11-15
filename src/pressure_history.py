"""Store pressure measurements and calculate a three-hour trend."""

import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

HISTORY_RETENTION = timedelta(hours=24)
TREND_PERIOD = timedelta(hours=3)
TREND_TOLERANCE = timedelta(minutes=15)
TREND_THRESHOLD_HPA = 0.5


def _parse_measurement(item):
    """Validate and normalize one pressure measurement."""
    try:
        pressure = float(item["pressure"])
        updated = datetime.fromisoformat(item["updated"])

        if not math.isfinite(pressure):
            return None

        if updated.tzinfo is None or updated.utcoffset() is None:
            return None

        return {
            "pressure": pressure,
            "updated": updated.astimezone(timezone.utc),
        }
    except (KeyError, ValueError, TypeError, OverflowError):
        return None


def load_history(path, now=None):
    """Load valid measurements from the last 24 hours."""
    now = now or datetime.now(timezone.utc)

    try:
        payload = json.loads(
            Path(path).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return []

    if not isinstance(payload, list):
        return []

    measurements = {}

    for item in payload:
        if not isinstance(item, dict):
            continue

        measurement = _parse_measurement(item)

        if measurement is None:
            continue

        updated = measurement["updated"]
        age = now - updated

        if timedelta(0) <= age <= HISTORY_RETENTION:
            measurements[updated] = measurement

    return [
        measurements[key]
        for key in sorted(measurements)
    ]


def save_measurement(path, pressure, updated, now=None):
    """Add a unique measurement and atomically save history."""
    now = now or datetime.now(timezone.utc)

    measurement = _parse_measurement({
        "pressure": pressure,
        "updated": updated.isoformat(),
    })

    if measurement is None:
        return []

    age = now - measurement["updated"]

    if not timedelta(0) <= age <= HISTORY_RETENTION:
        return load_history(path, now)

    history = load_history(path, now)

    measurements = {
        item["updated"]: item
        for item in history
    }

    existing = measurements.get(measurement["updated"])

    if existing is not None:
        if existing["pressure"] == measurement["pressure"]:
            return history

    measurements[measurement["updated"]] = measurement

    history = [
        measurements[key]
        for key in sorted(measurements)
    ]

    target = Path(path)
    temporary = target.with_suffix(target.suffix + ".tmp")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = [
            {
                "pressure": item["pressure"],
                "updated": item["updated"].isoformat(),
            }
            for item in history
        ]

        temporary.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

        os.replace(temporary, target)

    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass

    return history


def calculate_trend(history, now=None):
    """Return rising, steady, falling, or None."""
    now = now or datetime.now(timezone.utc)

    if not history:
        return None

    current = history[-1]

    if not timedelta(0) <= now - current["updated"] < timedelta(minutes=15):
        return None

    target_time = current["updated"] - TREND_PERIOD

    candidates = [
        item
        for item in history[:-1]
        if abs(item["updated"] - target_time) <= TREND_TOLERANCE
    ]

    if not candidates:
        return None

    previous = min(
        candidates,
        key=lambda item: abs(item["updated"] - target_time),
    )

    difference = current["pressure"] - previous["pressure"]

    if difference > TREND_THRESHOLD_HPA:
        return "rising"

    if difference < -TREND_THRESHOLD_HPA:
        return "falling"

    return "steady"
