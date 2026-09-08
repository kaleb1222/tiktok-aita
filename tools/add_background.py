"""add_background.py - add a looping background video to the render pool.

The workflow picks one file at random out of the GitHub release tagged
`assets` and drops it in as public/parkour.mp4, so growing the pool is purely
a matter of putting more files in that release. Remotion renders it with
objectFit:cover under a 38% dark overlay, muted and looping.

  python add_background.py <youtube-url> --name bg_subway1
  python add_background.py "ytsearch1:subway surfers gameplay no copyright" --name bg_subway2
  python add_background.py --list

Each clip is normalised before upload:
  * cropped/scaled to exactly 1080x1920 (the render size - anything else gets
    cropped by objectFit anyway, so bake it in and save bandwidth)
  * audio stripped entirely (the renderer mutes it; this roughly halves size)
  * trimmed to --minutes so one file cannot balloon the release
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

# Pexels contributor names carry arbitrary Unicode; on Windows the default
# cp1252 console encoding raises inside print() and kills the run *after* a
# clip has already downloaded. Cost one clip before this was added.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = "kaleb1222/tiktok-aita"
TAG = "assets"
SCRATCH = os.path.join(os.environ.get("TEMP", "/tmp"), "bgwork")


def token():
    """Reuse the PAT already embedded in the git remote - never printed."""
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        url = ""
    m = re.search(r"https://([^@]+)@", url)
    if not m:
        sys.exit("no token in the git remote; run from the repo clone")
    return m.group(1).split(":")[-1]


def api(path, tok, data=None, method=None, host="api.github.com", ctype=None):
    req = urllib.request.Request("https://%s%s" % (host, path), data=data, method=method)
    req.add_header("Authorization", "token " + tok)
    req.add_header("Accept", "application/vnd.github+json")
    if ctype:
        req.add_header("Content-Type", ctype)
    with urllib.request.urlopen(req, timeout=600) as r:
        body = r.read()
    return json.loads(body) if body else {}


def release(tok):
    return api("/repos/%s/releases/tags/%s" % (REPO, TAG), tok)


def cmd_list(tok):
    rel = release(tok)
    vids = [a for a in rel["assets"] if a["name"].lower().endswith(".mp4")]
    total = sum(a["size"] for a in vids)
    print("background pool: %d clips, %.0f MB total" % (len(vids), total / 1048576))
    for a in sorted(vids, key=lambda x: x["name"]):
        print("  %-30s %6.1f MB" % (a["name"], a["size"] / 1048576))


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def pexels_key():
    """Free key from pexels.com/api. Env var wins; otherwise a one-line file
    next to this script so it never lands in the repo."""
    k = os.environ.get("PEXELS_API_KEY", "").strip()
    if k:
        return k
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pexels_key")
    if os.path.exists(path):
        return open(path).read().strip()
    return ""


def pexels_search(query, count, minutes):
    """Portrait, HD, properly licensed for commercial use with no attribution.

    Chosen over YouTube because Google blocks yt-dlp outright now (403, then
    an n-challenge needing a Deno runtime, and android_vr only serves 360p),
    and because stock removes the copyright exposure that ripped gameplay
    carries.
    """
    key = pexels_key()
    if not key:
        sys.exit("no Pexels key. Get a free one at https://www.pexels.com/api/ "
                 "then: setx PEXELS_API_KEY <key>   (or write tools/.pexels_key)")
    url = ("https://api.pexels.com/videos/search?query=%s&orientation=portrait"
           "&size=medium&per_page=%d" % (urllib.parse.quote(query), max(count * 3, 15)))
    req = urllib.request.Request(url)
    req.add_header("Authorization", key)
    # Pexels' WAF 403s the default Python-urllib UA even with a valid key.
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; bg-fetch/1.0)")
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    out = []
    # Longest first: the renderer loops the clip under an ~80s script, so a
    # 15s source visibly repeats five times while a 50s one barely cycles.
    for v in sorted(data.get("videos", []), key=lambda x: -x.get("duration", 0)):
        if v.get("duration", 0) < 10:      # too short to loop without obvious repeats
            continue
        files = [f for f in v.get("video_files", [])
                 if f.get("height", 0) >= 1080 and f.get("width", 0) < f.get("height", 1)]
        if not files:
            continue
        files.sort(key=lambda f: -f["height"])
        out.append({"url": files[0]["link"], "id": v["id"],
                    "dur": v["duration"], "by": v.get("user", {}).get("name", "?")})
        if len(out) >= count:
            break
    if not out:
        sys.exit("no portrait HD results for %r" % query)
    return out


def fetch_url(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "bg-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)


def download(source, dest):
    """yt-dlp handles both direct URLs and ytsearch: queries."""
    import yt_dlp
    opts = {
        "outtmpl": dest,
        "format": "bestvideo[height>=1080]/bestvideo/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source, download=True)
    if "entries" in info:
        info = info["entries"][0]
    return info.get("title", "?"), info.get("duration", 0)


def normalise(src, dst, minutes):
    """1080x1920, no audio, length-capped. Scale up then centre-crop so the
    frame is filled whatever the source aspect ratio is."""
    vf = ("scale=1080:1920:force_original_aspect_ratio=increase,"
          "crop=1080:1920")
    cmd = [ffmpeg_exe(), "-y", "-i", src, "-t", str(int(minutes * 60)),
           "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0 or not os.path.exists(dst):
        sys.exit("ffmpeg failed:\n" + p.stderr[-1200:])


def upload(path, name, tok):
    rel = release(tok)
    for a in rel["assets"]:
        if a["name"] == name:
            print("  replacing existing %s" % name)
            api("/repos/%s/releases/assets/%d" % (REPO, a["id"]), tok, method="DELETE")
    with open(path, "rb") as f:
        blob = f.read()
    api("/repos/%s/releases/%d/assets?name=%s" % (REPO, rel["id"], name),
        tok, data=blob, method="POST", host="uploads.github.com",
        ctype="video/mp4")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", help="YouTube URL or ytsearch1:<query>")
    ap.add_argument("--file", help="normalise+upload an mp4 you already have")
    ap.add_argument("--stock", help="Pexels query, e.g. 'satisfying paint mixing'")
    ap.add_argument("--count", type=int, default=1, help="how many stock clips")
    ap.add_argument("--name", help="asset filename, e.g. bg_subway1")
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--keep", action="store_true", help="don't upload, just build the file")
    a = ap.parse_args()

    tok = token()
    if a.list or not (a.source or a.file or a.stock):
        cmd_list(tok)
        return

    os.makedirs(SCRATCH, exist_ok=True)

    # ── licensed stock, possibly several at once ──────────────────────────
    if a.stock:
        base = a.name or re.sub(r"[^a-z0-9]+", "_", a.stock.lower()).strip("_")
        base = base if base.startswith("bg_") else "bg_" + base
        for i, v in enumerate(pexels_search(a.stock, a.count, a.minutes), 1):
            name = "%s%d.mp4" % (base, i)
            raw = os.path.join(SCRATCH, "stock_%d.mp4" % v["id"])
            out = os.path.join(SCRATCH, name)
            print("[%d/%d] pexels #%s by %s (%ss)" % (i, a.count, v["id"], v["by"], v["dur"]))
            fetch_url(v["url"], raw)
            normalise(raw, out, a.minutes)
            print("   built %s (%.1f MB)" % (name, os.path.getsize(out) / 1048576))
            if not a.keep:
                upload(out, name, tok)
            for p in (raw, out):
                try:
                    os.remove(p)
                except Exception:
                    pass
        cmd_list(tok)
        return

    # ── a file already on disk ────────────────────────────────────────────
    if a.file:
        if not a.name:
            sys.exit("--name is required with --file")
        name = a.name if a.name.endswith(".mp4") else a.name + ".mp4"
        out = os.path.join(SCRATCH, name)
        print("normalising %s ..." % os.path.basename(a.file))
        normalise(a.file, out, a.minutes)
        print("  built %s (%.1f MB)" % (name, os.path.getsize(out) / 1048576))
        if not a.keep:
            upload(out, name, tok)
            cmd_list(tok)
        return

    if not a.name:
        sys.exit("--name is required (e.g. --name bg_subway1)")

    name = a.name if a.name.endswith(".mp4") else a.name + ".mp4"
    os.makedirs(SCRATCH, exist_ok=True)
    raw = os.path.join(SCRATCH, "raw.%(ext)s")
    out = os.path.join(SCRATCH, name)

    print("downloading ...")
    title, dur = download(a.source, raw)
    print("  source: %s (%ss)" % (title[:60], dur))

    got = None
    for f in os.listdir(SCRATCH):
        if f.startswith("raw."):
            got = os.path.join(SCRATCH, f)
            break
    if not got:
        sys.exit("download produced no file")

    print("normalising to 1080x1920, muted, %.0f min ..." % a.minutes)
    normalise(got, out, a.minutes)
    mb = os.path.getsize(out) / 1048576
    print("  built %s (%.1f MB)" % (name, mb))
    try:
        os.remove(got)
    except Exception:
        pass

    if a.keep:
        print("kept at %s (not uploaded)" % out)
        return
    print("uploading to release '%s' ..." % TAG)
    upload(out, name, tok)
    print("done. pool is now:")
    cmd_list(tok)


if __name__ == "__main__":
    main()
