"""
Fetches the top self-post URL from r/AmItheAsshole this week.

Requires env vars REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (Reddit app credentials).
Prints the post URL to stdout on success, exits 1 on failure.
"""
import base64
import json
import os
import sys
import urllib.request
import urllib.parse

SUBREDDIT = "AmItheAsshole"
USER_AGENT = "script:tiktok-aita-bot:v1.0 (by /u/kaleb1222)"


def get_oauth_token(client_id: str, client_secret: str) -> str:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=body,
        headers={
            "Authorization": f"Basic {credentials}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in response: {data}")
    return token


def fetch_top_post(token: str) -> str:
    url = f"https://oauth.reddit.com/r/{SUBREDDIT}/top.json?t=week&limit=25&raw_json=1"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()

    data = json.loads(raw)
    posts = data["data"]["children"]
    filtered = [
        p["data"]["url"] for p in posts
        if not p["data"]["stickied"] and p["data"].get("is_self")
    ]
    if not filtered:
        raise RuntimeError("No eligible self-posts found in top 25")
    return filtered[0]


def main():
    client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("ERROR: REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars required", file=sys.stderr)
        print("Create a Reddit app at: https://www.reddit.com/prefs/apps", file=sys.stderr)
        sys.exit(1)

    try:
        token = get_oauth_token(client_id, client_secret)
    except Exception as e:
        print(f"ERROR: Failed to get Reddit OAuth token: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        url = fetch_top_post(token)
    except Exception as e:
        print(f"ERROR: Failed to fetch top post: {e}", file=sys.stderr)
        sys.exit(1)

    print(url)


if __name__ == "__main__":
    main()
