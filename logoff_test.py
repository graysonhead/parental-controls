#!/usr/bin/env python3
"""Standalone logoff test. Running this WILL end your graphical session."""

import subprocess
import sys
import time

DELAY = 5  # shorter delay for testing

print(f"Logging out in {DELAY}s...")
time.sleep(DELAY)

# Ask KDE to do a clean logout (no confirmation dialog)
result = subprocess.run(
    ["qdbus", "org.kde.Shutdown", "/Shutdown", "logout"],
    capture_output=True, text=True,
)
print(f"qdbus exit: {result.returncode} {result.stderr.strip()}")

time.sleep(3)
print("Still alive — qdbus logout may not have worked", file=sys.stderr)
