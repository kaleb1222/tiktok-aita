"""Prints the URL of the top self-post from r/AmItheAsshole this week."""
import json
import sys

with open('/tmp/reddit.json') as f:
    posts = json.load(f)['data']['children']

filtered = [
    p['data']['url'] for p in posts
    if not p['data']['stickied'] and p['data'].get('is_self')
]

if not filtered:
    print("No suitable posts found", file=sys.stderr)
    sys.exit(1)

print(filtered[0])
