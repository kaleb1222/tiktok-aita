"""
Auto-downloader for TikTok AITA videos.
Checks GitHub Actions artifacts and saves new MP4s to the Downloads folder.
Run on a schedule (Task Scheduler) to auto-collect every video.

Setup (one time):
  python download_videos.py --setup
"""

import urllib.request
import urllib.error
import json
import os
import zipfile
import io
import sys
import argparse

OWNER = "kaleb1222"
REPO = "tiktok-aita"
DOWNLOAD_DIR = r"C:\Users\Kaleb\Downloads\tiktok aiti"
TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".tiktok_github_token")
LOG_FILE = os.path.join(DOWNLOAD_DIR, ".downloaded.txt")


def load_token():
    if not os.path.exists(TOKEN_FILE):
        print("GitHub token not found. Run:  python download_videos.py --setup")
        sys.exit(1)
    return open(TOKEN_FILE).read().strip()


def api_get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "tiktok-aita-downloader",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


class _StripAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """Strip Authorization header when redirecting away from github.com (e.g. to Azure Blob)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req and "github.com" not in newurl:
            new_req.headers.pop("Authorization", None)
            new_req.unredirected_hdrs.pop("Authorization", None)
        return new_req


def download_artifact_zip(download_url, token):
    """Download artifact ZIP — GitHub redirects to Azure; strip auth header on redirect."""
    req = urllib.request.Request(download_url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "tiktok-aita-downloader",
    })
    opener = urllib.request.build_opener(_StripAuthOnRedirect)
    with opener.open(req, timeout=120) as r:
        return r.read()


def load_downloaded():
    if not os.path.exists(LOG_FILE):
        return set()
    return set(open(LOG_FILE).read().splitlines())


def save_downloaded(ids):
    with open(LOG_FILE, "w") as f:
        f.write("\n".join(sorted(ids)))


def run():
    token = load_token()
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    downloaded = load_downloaded()

    print(f"Checking artifacts for {OWNER}/{REPO}...")
    data = api_get(f"https://api.github.com/repos/{OWNER}/{REPO}/actions/artifacts?per_page=20", token)
    artifacts = data.get("artifacts", [])

    new_count = 0
    for artifact in artifacts:
        art_id = str(artifact["id"])
        name = artifact["name"]
        if art_id in downloaded:
            continue
        if artifact.get("expired"):
            downloaded.add(art_id)
            continue
        if not name.startswith("tiktok-video-"):
            continue

        print(f"  Downloading: {name}...")
        try:
            zip_bytes = download_artifact_zip(artifact["archive_download_url"], token)
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
            mp4_files = [n for n in zf.namelist() if n.endswith(".mp4")]
            for mp4 in mp4_files:
                dest = os.path.join(DOWNLOAD_DIR, os.path.basename(mp4))
                # Don't overwrite existing files
                if os.path.exists(dest):
                    base, ext = os.path.splitext(dest)
                    dest = f"{base}_{art_id}{ext}"
                with open(dest, "wb") as f:
                    f.write(zf.read(mp4))
                print(f"    Saved: {os.path.basename(dest)}")
            downloaded.add(art_id)
            new_count += 1
        except Exception as e:
            print(f"    Error: {e}")

    save_downloaded(downloaded)
    if new_count == 0:
        print("  No new videos.")
    else:
        print(f"  Done — {new_count} new video(s) saved to {DOWNLOAD_DIR}")


def setup():
    print("=== TikTok AITA Video Downloader Setup ===")
    print()
    print("You need a GitHub Personal Access Token.")
    print("Create one at: https://github.com/settings/tokens/new")
    print("Required scope: repo (or just 'actions' read)")
    print()
    token = input("Paste your token here: ").strip()
    if not token:
        print("No token entered. Aborting.")
        sys.exit(1)
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    print(f"Token saved to {TOKEN_FILE}")
    print()
    print("Testing token...")
    try:
        data = api_get(f"https://api.github.com/repos/{OWNER}/{REPO}", token)
        print(f"Connected to repo: {data['full_name']}")
        print("Setup complete!")
    except Exception as e:
        print(f"Error: {e} — check your token and try again.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true", help="First-time setup")
    args = parser.parse_args()
    if args.setup:
        setup()
    else:
        run()
