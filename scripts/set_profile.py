import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_FILE = REPO_ROOT / "profile.txt"
ENV_FILE = REPO_ROOT / "app.env"
URL = "http://127.0.0.1:8000/profile"


def read_api_key():
    if not ENV_FILE.is_file():
        sys.exit("app.env was not found in the repository root.")
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                return value
    sys.exit("API_KEY is missing or empty in app.env.")


def read_draft():
    if not PROFILE_FILE.is_file():
        sys.exit("profile.txt was not found in the repository root.")
    try:
        content = PROFILE_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        sys.exit("profile.txt could not be read as UTF-8 text.")
    if not content.strip():
        sys.exit("profile.txt is empty.")
    return content


def main():
    api_key = read_api_key()
    content = read_draft()
    try:
        response = httpx.put(
            URL,
            headers={"X-API-Key": api_key},
            json={"content": content},
            timeout=10,
        )
    except httpx.ConnectError:
        sys.exit("The server is not reachable at http://127.0.0.1:8000. Start it and try again.")
    except httpx.HTTPError:
        sys.exit("The request failed before a response was received.")
    if response.status_code == 401:
        sys.exit("The server rejected the API key (401). Check API_KEY in app.env and restart the server.")
    if response.status_code == 422:
        sys.exit("The server rejected the profile (422). It must be 1 to 2000 characters after trimming and must not contain NUL characters.")
    if response.status_code != 200:
        sys.exit(f"Unexpected response from the server: {response.status_code}")
    body = response.json()
    redactions = body["redactions"]
    print("status:", response.status_code)
    print("char_count:", body["char_count"])
    print(
        "redactions:",
        f"emails={redactions['emails']}",
        f"phones={redactions['phones']}",
        f"lines={redactions['lines']}",
    )
    if body["warnings"]:
        for warning in body["warnings"]:
            print("warning:", warning)
    else:
        print("warnings: none")


if __name__ == "__main__":
    main()
