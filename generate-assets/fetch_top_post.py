"""
Fetches the top self-post URL from r/AmItheAsshole this week.
Prints the post URL to stdout on success, exits 1 on failure.
"""
import json
import sys
import urllib.request

USER_AGENT = "script:tiktok-aita-bot:v1.0 (by /u/kaleb1222)"
URL = "https://www.reddit.com/r/AmItheAsshole/top.json?t=week&limit=10&raw_json=1"


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"ERROR: Reddit request failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not raw:
        print("ERROR: Reddit returned empty response", file=sys.stderr)
        sys.exit(1)

    # Detect HTML (consent/login page) instead of JSON
    if raw[:1] != b"{":
        print(f"ERROR: Reddit returned non-JSON (first 200 bytes): {raw[:200]}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON parse failed: {e}", file=sys.stderr)
        sys.exit(1)

    posts = data["data"]["children"]
    filtered = [
        p["data"]["url"] for p in posts
        if not p["data"]["stickied"] and p["data"].get("is_self")
    ]

    if not filtered:
        print("ERROR: No eligible self-posts found", file=sys.stderr)
        sys.exit(1)

    print(filtered[0])


if __name__ == "__main__":
    fetch()
