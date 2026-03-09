#!/usr/bin/env python3
"""Install Alpha Hunter Dashboard as a macOS LaunchAgent."""

import os, subprocess, sys

PLIST_LABEL = "ai.alphahunter.dashboard"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable

plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{PYTHON}</string>
        <string>{REPO_DIR}/dashboard/app.py</string>
    </array>
    <key>WorkingDirectory</key><string>{REPO_DIR}</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>/tmp/alpha-hunter/dashboard.log</string>
    <key>StandardErrorPath</key><string>/tmp/alpha-hunter/dashboard.log</string>
    <key>ThrottleInterval</key><integer>10</integer>
</dict>
</plist>"""

with open(PLIST_PATH, "w") as f:
    f.write(plist)

subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)
result = subprocess.run(["launchctl", "load", PLIST_PATH], capture_output=True, text=True)
if result.returncode == 0:
    print(f"✓ Dashboard running at http://localhost:5050")
    print(f"  Auto-starts on reboot")
else:
    print(f"✗ {result.stderr}")

if __name__ == "__main__":
    pass
