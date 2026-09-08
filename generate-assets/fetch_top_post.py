"""Picks what the next video is about and caches it for run.py.

Used to be AITA-only. Now it asks content_sources for whichever format is due
in the rotation, so the account posts a mix instead of one note forever.

Contract is unchanged, so the GitHub workflow needs no edits:
  - writes {url,id,title,selftext,kind} to /tmp/reddit_post.json
  - prints a URL containing /comments/<id>/ to stdout (the workflow greps the
    id out of it for the used-posts cache; non-Reddit kinds emit a synthetic
    URL in the same shape so that sed keeps working)
  - exits 1 on failure

  python fetch_top_post.py            next item in the rotation
  python fetch_top_post.py --kind X   force one kind (aita, tifu, wyr, ...)
  python fetch_top_post.py --plan     show the rotation, fetch nothing
"""
import json
import os
import sys

import content_sources as cs

CACHE_FILE = cs.CACHE_FILE


def load_used_ids():
    path = os.environ.get("USED_POSTS_FILE", "")
    if not path or not os.path.exists(path):
        return set()
    with open(path) as f:
        return {line.strip() for line in f if line.strip()}


def main():
    offset = int(os.environ.get("GITHUB_RUN_NUMBER", "0"))

    if "--plan" in sys.argv:
        print("rotation (%d slots):" % len(cs.ROTATION))
        for i in range(len(cs.ROTATION)):
            mark = " <- next" if i == offset % len(cs.ROTATION) else ""
            print("  %2d %s%s" % (i, cs.ROTATION[i], mark))
        return

    used_ids = load_used_ids()
    try:
        if "--kind" in sys.argv:
            kind = sys.argv[sys.argv.index("--kind") + 1]
            post = cs.fetch(kind, used_ids, offset)
        else:
            post = cs.fetch_with_fallback(used_ids, offset)
    except Exception as e:
        print("ERROR: %s" % e, file=sys.stderr)
        sys.exit(1)

    with open(CACHE_FILE, "w") as f:
        json.dump(post, f)

    print("kind=%s title=%s" % (post["kind"], post["title"][:60]), file=sys.stderr)
    print(post["url"])


if __name__ == "__main__":
    main()
