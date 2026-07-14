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
RSS_FEEDS = [
    f"https://www.reddit.com/r/{SUBREDDIT}/top/.rss?t=week&limit=100",
    f"https://www.reddit.com/r/{SUBREDDIT}/top/.rss?t=month&limit=100",
]
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
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    eligible = []
    seen = set()
    for feed in RSS_FEEDS:
        try:
            req = urllib.request.Request(feed, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp:
                root = ET.fromstring(resp.read())
        except Exception as e:
            print(f"feed error {feed}: {e}", file=sys.stderr)
            continue

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
            # Skip follow-up "UPDATE" + meta/forum posts — they reference a prior
            # story and don't work as a standalone ~1-minute video.
            if re.search(r"(?i)\bupdate\b", title) or "[meta]" in low or "open forum" in low:
                continue
            post_id = post_id_from_url(url)
            if post_id in used_ids or post_id in seen:
                continue
            selftext = strip_html(content_html)
            if len(selftext) < 50:
                continue
            seen.add(post_id)
            eligible.append({"url": url, "title": title, "selftext": selftext, "id": post_id})

    if not eligible:
        raise RuntimeError("No eligible self-posts found in RSS feeds")

    # Pick a DIFFERENT post per run so many parallel runs render distinct videos
    # (GITHUB_RUN_NUMBER is unique+monotonic per run; falls back to 0 locally).
    offset = int(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    return eligible[offset % len(eligible)]


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
