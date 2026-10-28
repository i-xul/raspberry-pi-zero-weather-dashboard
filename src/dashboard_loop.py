#!/usr/bin/env python3
"""Refresh the COSY BARO e-paper dashboard every five minutes."""

import logging
import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "epaper_dashboard.py"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

while True:
    logging.info("Starting e-paper dashboard refresh")

    try:
        result = subprocess.run(
            ["/usr/bin/python3", str(SCRIPT)],
            check=False,
            timeout=120,
        )

        if result.returncode == 0:
            logging.info("E-paper dashboard refresh completed successfully")
        else:
            logging.error(
                "E-paper dashboard refresh failed with exit code %s",
                result.returncode,
            )

    except subprocess.TimeoutExpired:
        logging.error("E-paper dashboard refresh timed out after 120 seconds")

    except OSError:
        logging.exception("Failed to start e-paper dashboard process")

    time.sleep(300)
