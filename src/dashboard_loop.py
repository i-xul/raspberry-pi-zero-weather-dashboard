#!/usr/bin/env python3
"""Refresh the COSY BARO e-paper dashboard every five minutes."""

import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "epaper_dashboard.py"

while True:
    subprocess.run(["/usr/bin/python3", str(SCRIPT)], check=False)
    time.sleep(300)
