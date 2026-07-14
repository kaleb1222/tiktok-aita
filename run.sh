#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Get Reddit URL ────────────────────────────────────────────────────────────
if [ "${1:-}" != "" ]; then
  POST_URL="$1"
else
  echo "Fetching top AITA post from this week..."
  POST_URL=$(curl -s -A "Mozilla/5.0 (compatible; aita-bot/1.0)" \
    "https://old.reddit.com/r/AmItheAsshole/top.json?t=week&limit=10" | \
    python3 -c "
import json, sys
posts = json.load(sys.stdin)['data']['children']
filtered = [p['data']['url'] for p in posts
            if not p['data']['stickied'] and p['data'].get('is_self', False)]
print(filtered[0])
")
fi

echo "Processing: $POST_URL"

# ── Generate audio + script.json ─────────────────────────────────────────────
cd "$SCRIPT_DIR/generate-assets"
python3 run.py "$POST_URL"

# ── Copy assets into Remotion public/ ────────────────────────────────────────
WORKSPACE=$(ls -dt "$SCRIPT_DIR/generate-assets/workspace/"*/ | head -1)
echo "Workspace: $WORKSPACE"

mkdir -p "$SCRIPT_DIR/video-generator/public/sounds"
cp "$WORKSPACE/script.json" "$SCRIPT_DIR/video-generator/public/script.json"
cp "$WORKSPACE/sounds/"*.mp3 "$SCRIPT_DIR/video-generator/public/sounds/"

# ── Render video ──────────────────────────────────────────────────────────────
cd "$SCRIPT_DIR/video-generator"

if [ ! -f "public/parkour.mp4" ]; then
  echo ""
  echo "ERROR: public/parkour.mp4 not found."
  echo "Add a royalty-free Minecraft parkour video as video-generator/public/parkour.mp4"
  echo "See video-generator/public/README.md for instructions."
  exit 1
fi

OUTPUT=$(python3 -c "import json; d=json.load(open('public/script.json')); print(d['title']['filename'])")
BASE="${OUTPUT%.mp4}"
mkdir -p out

echo "Rendering Part 1 to: out/${BASE}_part1.mp4"
npx remotion render src/index.tsx Part1 "out/${BASE}_part1.mp4"

echo "Rendering Part 2 to: out/${BASE}_part2.mp4"
npx remotion render src/index.tsx Part2 "out/${BASE}_part2.mp4"

echo ""
echo "Done!"
echo "  Part 1: video-generator/out/${BASE}_part1.mp4"
echo "  Part 2: video-generator/out/${BASE}_part2.mp4"
