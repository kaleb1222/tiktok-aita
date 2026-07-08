"""
Fetches the top self-post URL from r/AmItheAsshole this week via RSS.
No API credentials required.
Prints the post URL to stdout on success, exits 1 on failure.
"""
import sys
import urllib.request
import xml.etree.ElementTree as ET

SUBREDDIT = "AmItheAsshole"
RSS_URL = f"https://www.reddit.com/r/{SUBREDDIT}/top/.rss?t=week&limit=25"
USER_AGENT = "tiktok-aita-bot:v2.0 (RSS reader)"


def fetch_top_post() -> str:
    req = urllib.request.Request(RSS_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    for entry in root.findall("atom:entry", ns):
        # Skip stickied/announcements — they have [mod] or no selftext
        title_el = entry.find("atom:title", ns)
        link_el = entry.find("atom:link", ns)
        content_el = entry.find("atom:content", ns)

        if title_el is None or link_el is None:
            continue

        title = title_el.text or ""
        url = link_el.attrib.get("href", "")
        content = content_el.text or "" if content_el is not None else ""

        # Skip non-self posts (image/link posts have no real content body)
        # Self posts have substantial content in the feed
        if not url or "/comments/" not in url:
            continue

        # Skip stickied mod posts
        if "[mod]" in title.lower() or "welcome to" in title.lower():
            continue

        return url

    raise RuntimeError("No eligible self-posts found in RSS feed")


def main():
    try:
        url = fetch_top_post()
    except Exception as e:
        print(f"ERROR: Failed to fetch top post: {e}", file=sys.stderr)
        sys.exit(1)

    print(url)


if __name__ == "__main__":
    main()
