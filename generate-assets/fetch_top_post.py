"""
Fetches the top self-post from r/AmItheAsshole this week via RSS.
Skips posts already listed in USED_POSTS_FILE (env var, one ID per line).
Writes full post data (url, title, selftext) to /tmp/reddit_post.json
so run.py can consume it without making a second Reddit request.
Prints the post URL to stdout on success, exits 1 on failure.
"""
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape

SUBREDDIT = "AmItheAsshole"
RSS_URL = f"https://www.reddit.com/r/{SUBREDDIT}/top/.rss?t=week&limit=25"
USER_AGENT = "tiktok-aita-bot:v2.0 (RSS reader)"
CACHE_FILE = "/tmp/reddit_post.json"


def strip_html(html: str) -> str:
    text = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def load_used_ids() -> set:
    path = os.environ.get("USED_POSTS_FILE", "")
    if not path or not os.path.exists(path):
        return set()
    with open(path) as f:
        return {line.strip() for line in f if line.strip()}


def post_id_from_url(url: str) -> str:
    m = re.search(r"/comments/([^/]+)", url)
    return m.group(1) if m else ""


def fetch_top_post(used_ids: set) -> dict:
    req = urllib.request.Request(RSS_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        link_el = entry.find("atom:link", ns)
        content_el = entry.find("atom:content", ns)

        if title_el is None or link_el is None:
            continue

        title = (title_el.text or "").strip()
        url = link_el.attrib.get("href", "")
        content_html = content_el.text or "" if content_el is not None else ""

        if not url or "/comments/" not in url:
            continue
        low = title.lower()
        if "[mod]" in low or "welcome to" in low:
            continue
        # Skip follow-up "UPDATE" posts + meta/forum posts — they reference a
        # prior story and don't work as a standalone ~1-minute video.
        if re.search(r"(?i)\bupdate\b", title) or "[meta]" in low or "open forum" in low:
            continue

        post_id = post_id_from_url(url)
        if post_id in used_ids:
            print(f"Skipping already-used post: {post_id}", file=sys.stderr)
            continue

        selftext = strip_html(content_html)
        # RSS wraps content in an outer div — skip if content is essentially empty
        if len(selftext) < 50:
            continue

        return {"url": url, "title": title, "selftext": selftext, "id": post_id}

    raise RuntimeError("No eligible self-posts found in RSS feed")


def main():
    used_ids = load_used_ids()
    try:
        post = fetch_top_post(used_ids)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Write full data so run.py can read it without hitting Reddit again
    with open(CACHE_FILE, "w") as f:
        json.dump(post, f)

    print(post["url"])


if __name__ == "__main__":
    main()
