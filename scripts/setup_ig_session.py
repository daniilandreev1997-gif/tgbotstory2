"""One-time script: login to Instagram and save session to D:/AI/secrets/ig-session.json.

Run this ONCE. Enter IG credentials. The session file is used by the bot for
HTTP-only story fetching (no Selenium/browser needed).

Credentials are NOT stored in the repo — only the session file goes to
D:/AI/secrets/ig-session.json.
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SECRETS_DIR = Path(os.environ.get("SECRETS_DIR", "D:/AI/secrets"))
SESSION_FILE = SECRETS_DIR / "ig-session.json"
CREDS_FILE = SECRETS_DIR / "ig-credentials.txt"


def main() -> None:
    print("=" * 60)
    print("Instagram session setup for tgbotstory2")
    print("=" * 60)
    print()

    # Check for saved credentials
    username: str = ""
    password: str = ""

    if CREDS_FILE.exists():
        lines = CREDS_FILE.read_text().strip().split("\n")
        if len(lines) >= 2:
            username = lines[0].strip()
            password = lines[1].strip()
            print(f"[INFO] Found saved credentials for: {username}")
            use_saved = input("Use saved credentials? [Y/n]: ").strip().lower()
            if use_saved == "n":
                username = ""
                password = ""

    if not username:
        print()
        print("Enter your Instagram credentials (they will be saved in")
        print(f"  {CREDS_FILE}")
        print("for future use — NEVER committed to git.")
        print()
        username = input("Instagram username: ").strip()
        password = getpass.getpass("Instagram password: ").strip()

        if not username or not password:
            print("[ERROR] Username and password are required.")
            sys.exit(1)

        # Save credentials
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        CREDS_FILE.write_text(f"{username}\n{password}")
        print(f"[OK] Credentials saved to {CREDS_FILE}")

    # Install instagrapi if needed
    try:
        from instagrapi import Client
    except ImportError:
        print("[INFO] Installing instagrapi...")
        os.system(f"{sys.executable} -m pip install instagrapi -q")
        from instagrapi import Client

    print()
    print(f"[...] Logging in as @{username} ...")

    client = Client()
    try:
        client.login(username, password)
        print(f"[OK] Logged in successfully!")
    except Exception as exc:
        print(f"[ERROR] Login failed: {exc}")
        sys.exit(1)

    # Save session
    client.dump_settings(SESSION_FILE)
    print(f"[OK] Session saved to {SESSION_FILE}")
    print()
    print("=" * 60)
    print("Setup complete! The bot will now use HTTP-only IG stories.")
    print(f"Session file: {SESSION_FILE}")
    print(f"Credentials:  {CREDS_FILE}")
    print()
    print("Both files are in D:/AI/secrets/ — NEVER committed to git.")
    print("=" * 60)


if __name__ == "__main__":
    main()