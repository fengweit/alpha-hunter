#!/usr/bin/env python3
"""
Install Alpha Hunter as a macOS LaunchAgent.
Runs 24/7, survives reboots, auto-restarts on crash.
"""

import os
import subprocess
import sys

PLIST_LABEL = "ai.alphahunter.runner"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
LOG_DIR = "/tmp/alpha-hunter"


def install():
    os.makedirs(LOG_DIR, exist_ok=True)

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{PYTHON}</string>
        <string>{REPO_DIR}/runner.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{REPO_DIR}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>{LOG_DIR}/stdout.log</string>

    <key>StandardErrorPath</key>
    <string>{LOG_DIR}/stderr.log</string>

    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>"""

    # Write plist
    with open(PLIST_PATH, "w") as f:
        f.write(plist)
    print(f"✓ LaunchAgent written: {PLIST_PATH}")

    # Unload if already running
    subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)

    # Load
    result = subprocess.run(["launchctl", "load", PLIST_PATH], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ Alpha Hunter loaded and running 24/7")
        print(f"  Logs: {LOG_DIR}/runner.log")
        print(f"  Stop: launchctl unload {PLIST_PATH}")
        print(f"  Status: launchctl list | grep alphahunter")
    else:
        print(f"✗ Failed to load: {result.stderr}")


def uninstall():
    subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)
    if os.path.exists(PLIST_PATH):
        os.remove(PLIST_PATH)
    print("✓ Alpha Hunter uninstalled")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        uninstall()
    else:
        install()
