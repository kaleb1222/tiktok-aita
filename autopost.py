"""autopost.py — headless TikTok poster for the AITA pipeline.

Runs on the PC via Task Scheduler at the optimal posting slots. Picks the
oldest video in "Downloads/tiktok aiti" not yet in posted.txt, builds the
deterministic SEO caption, and posts it publicly through TikTok Studio's web
uploader with a headless browser using the saved login session.

  python autopost.py --login     one-time: visible window to log in to TikTok
  python autopost.py --dry       show what would be posted
  python autopost.py             post the next video headlessly
  python autopost.py --private   same but posts as "Only you" (for testing)

Failures never mark a video as posted; a Discord ping (via the VM) reports
success or failure either way. Debug screenshots land in ./autopost-debug/.
"""
import hashlib
import os
import random
import re
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = r"C:\Users\Kaleb\Downloads\tiktok aiti"
POSTED = os.path.join(BASE, "posted.txt")
LAST_POST = os.path.join(BASE, "last_post.txt")
PROFILE = os.path.join(BASE, ".browser")
DEBUG = os.path.join(BASE, "autopost-debug")
VM = "root@167.233.161.154"
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=creator_center"
BURNDOWN_FLOOR = 10          # stop the extra daily slot once queue hits this
BURNDOWN_TASK = "TikTok Auto-Post Burndown"
MIN_GAP_SEC = 2.5 * 3600     # never post twice within this window (anti-burst)
MAX_JITTER_SEC = 20 * 60     # randomize the exact posting minute
NOWIN = 0x08000000 if os.name == "nt" else 0  # hide child consoles under pythonw


def keep_awake(on):
    """Hold the system awake only while actually posting, so a wake-timer run
    can finish before the unattended-sleep timeout puts the PC back to sleep."""
    if os.name != "nt":
        return
    import ctypes
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(
        (ES_CONTINUOUS | ES_SYSTEM_REQUIRED) if on else ES_CONTINUOUS)

# Hook LEADS the caption (first thing viewers + TikTok search read) — curiosity gap.
HOOKS = [
    "Wait until you hear how this ends \U0001F633",
    "This one made my jaw DROP \U0001F62E",
    "The audacity in this story is UNREAL \U0001F480",
    "I did NOT see that ending coming \U0001F92F",
    "You'll be FURIOUS after this one \U0001F624",
    "Reddit did NOT hold back on this \U0001F440",
    "The comments went CRAZY on this one \U0001F525",
    "This family drama is next level \U0001F62C",
]
# CTAs ask for a verdict — comments are the strongest reach signal for this niche.
CTAS = [
    "NTA or YTA? Tell me below \U0001F447",
    "Whose side are you on? \U0001F447",
    "Was that wrong?? Drop your verdict ⚖️",
    "What would YOU have done? \U0001F4AC",
]
# One focused, readable hashtag block (5 core + 1 rotating) — TikTok favors a tight,
# relevant set over a wall of tags.
NICHE_TAGS = ["#redditreadings", "#familydrama", "#amitheasshole",
              "#redditstorytime", "#aitareddit", "#storytimes"]


def clean_situation(name):
    """Turn the (often truncated) filename into readable caption text:
    normalize the AITA prefix, restore obvious apostrophes, drop junk."""
    t = os.path.splitext(name)[0]
    t = re.sub(r"^AITA_", "", t)
    t = re.sub(r"_Reddit_Story_Storytime.*$", "", t)
    t = t.replace("_", " ")
    t = re.sub(r"(?i)am i the a[- ]?hole[a-z]?", "AITA", t)
    t = re.sub(r"(?i)would i be the a[- ]?hole", "WIBTA", t)
    # "my ex s" -> "my ex's", "he s" -> "he's" (common possessive/contraction artifact)
    t = re.sub(r"\b([A-Za-z]{2,}) s\b", r"\1's", t)
    t = re.sub(r"\s+", " ", t).strip()
    if t and not t.endswith("?"):
        t += "..."
    return t


def part_of(name):
    """1 / 2 for a split story, else None."""
    m = re.search(r"-part([12])\.mp4$", name, re.I)
    return int(m.group(1)) if m else None


def caption_for(name):
    seed = int(hashlib.md5(name.encode()).hexdigest(), 16)
    hook = HOOKS[seed % len(HOOKS)]
    cta = CTAS[(seed // 7) % len(CTAS)]
    niche = NICHE_TAGS[(seed // 11) % len(NICHE_TAGS)]
    tags = "#aita #redditstories #storytime #reddit #fyp " + niche
    part = part_of(name)
    if part == 1:
        # flag that a second half is coming so viewers come back for it
        hook = "PART 1 👉 " + hook
        cta = "Part 2 is up next 👀 " + cta
        tags += " #part1"
    elif part == 2:
        # lead with PART 2 so it reads as the payoff, not a repost
        hook = "PART 2 🔥 (watch Part 1 first!)"
        cta = "Now you know the ending — " + cta
        tags += " #part2"
    # hook first, clean story teaser, verdict CTA, focused tags
    return "%s\n\n%s\n\n%s\n\n%s" % (hook, clean_situation(name), cta, tags)


def notify(msg):
    try:
        subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", VM,
                        "python3 /opt/tiktok-poster/notify.py " +
                        "'" + msg.replace("'", "'\\''") + "'"],
                       capture_output=True, timeout=60, creationflags=NOWIN)
    except Exception:
        pass


def readlines(p):
    try:
        return [l.strip() for l in open(p, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        return []


def next_video():
    vids = sorted(f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(".mp4"))
    done = set(readlines(POSTED))
    todo = [v for v in vids if v not in done]
    return (todo[0], len(todo)) if todo else (None, 0)


def login():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(PROFILE, headless=False,
                                                    channel="chrome",
                                                    viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto("https://www.tiktok.com/login")
        print("Log in to TikTok in the window, then close the window.")
        try:
            page.wait_for_event("close", timeout=600000)
        except Exception:
            pass
        ctx.close()
        print("Session saved.")


def post(video_path, caption, private=False):
    from playwright.sync_api import sync_playwright
    os.makedirs(DEBUG, exist_ok=True)
    shot = os.path.join(DEBUG, time.strftime("%Y%m%d-%H%M%S") + ".png")
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            PROFILE, headless=True,
            channel="chrome",
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        page = ctx.new_page()

        def kill_overlays():
            # TikTok's first-run "joyride" tour + tooltip layers steal clicks
            page.evaluate("""() => {
                for (const sel of ['#react-joyride-portal',
                                   '.react-joyride__overlay',
                                   'div[data-test-id="overlay"]']) {
                    document.querySelectorAll(sel).forEach(e => e.remove());
                }
            }""")

        try:
            page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector('input[type="file"]', state="attached", timeout=60000)
            if "/login" in page.url:
                raise RuntimeError("session expired - run: python autopost.py --login")

            # A previous failed run can leave an unsaved draft; TikTok then greets
            # every later visit with "A video you were editing wasn't saved.
            # Continue editing?" which blocks the uploader. Discard it, otherwise
            # each failure strands another draft and posting never recovers.
            try:
                discard = page.get_by_role("button", name=re.compile(r"^Discard$", re.I))
                if discard.count():
                    discard.first.click(timeout=5000)
                    print("  discarded a leftover draft", flush=True)
                    page.wait_for_timeout(2000)
                    page.wait_for_selector('input[type="file"]', state="attached", timeout=30000)
            except Exception as e:
                print("  draft-banner check skipped:", e, flush=True)

            # Attach the file, then CONFIRM it took. A silent no-op here (the
            # SPA re-rendering under us) otherwise burns the full upload timeout
            # and loses the slot, leaving a pristine "Select video" page.
            base = os.path.basename(video_path)
            attached = False
            for attempt in range(1, 4):
                page.set_input_files('input[type="file"]', video_path)
                try:
                    page.wait_for_function(
                        r"""(n) => { const t = document.body.innerText;
                            return t.includes(n.slice(0, 24)) ||
                                   /Uploading|Uploaded|\d+%|Cancel/.test(t); }""",
                        arg=base, timeout=45000)
                    attached = True
                    break
                except Exception:
                    print("  attach didn't take (try %d/3), retrying" % attempt, flush=True)
                    page.reload(wait_until="domcontentloaded")
                    page.wait_for_selector('input[type="file"]', state="attached", timeout=30000)
            if not attached:
                raise RuntimeError("file never attached to the uploader after 3 tries")

            # wait for the upload to reach 100% - the "Cancel/uploading" state
            # must clear before the Post button will actually submit
            page.wait_for_function(
                """() => { const t = document.body.innerText;
                    if (/Upload failed|processing failed/i.test(t)) return true;
                    return /Uploaded|100%/.test(t) &&
                           !/left|Uploading/i.test(t); }""",
                timeout=900000)
            if re.search(r"(?i)upload failed|processing failed", page.inner_text("body")):
                raise RuntimeError("TikTok reported upload/processing failure")
            time.sleep(3)
            kill_overlays()

            # caption box is a DraftJS rich editor - focus, select-all, delete,
            # then type. filling raw does not clear the pre-filled filename.
            box = page.locator('div[contenteditable="true"]').first
            box.click()
            time.sleep(0.5)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            time.sleep(0.5)
            page.keyboard.type(caption, delay=8)
            time.sleep(1)

            if private:
                try:
                    kill_overlays()
                    page.get_by_text(re.compile("^Who can watch this video", re.I)).scroll_into_view_if_needed(timeout=5000)
                    page.locator('div:has-text("Everyone")').last.click(timeout=6000)
                    page.get_by_text(re.compile("^Only you$", re.I)).click(timeout=6000)
                    time.sleep(1)
                except Exception:
                    print("note: could not set Only-you privacy")

            kill_overlays()
            btn = page.locator('button[data-e2e="post_video_button"]')
            if not btn.count():
                btn = page.get_by_role("button", name=re.compile(r"^Post$", re.I))
            btn.first.click(timeout=20000)

            # "We're still checking your video... Post now?" confirm dialog
            try:
                page.get_by_role("button", name=re.compile(r"^Post now$", re.I)).click(timeout=8000)
            except Exception:
                pass

            # success = redirected to content manager or a success toast/dialog
            page.wait_for_function(
                """() => location.pathname.includes('/content') ||
                         /your video has been|posted|Manage your posts/i
                            .test(document.body.innerText)""",
                timeout=180000)
            time.sleep(2)
            page.screenshot(path=shot)
            return True, shot
        except Exception as e:
            try:
                page.screenshot(path=shot)
            except Exception:
                pass
            return False, "%s (screenshot: %s)" % (e, shot)
        finally:
            ctx.close()


def recent_post_gap():
    try:
        return time.time() - float(open(LAST_POST).read().strip())
    except Exception:
        return 1e9


def stamp_post():
    open(LAST_POST, "w").write(str(time.time()))


def stop_burndown_if_done(remaining):
    """Once the queue reaches the floor, delete the extra daily slot so we
    drop back to the normal 2/day cadence automatically."""
    if remaining > BURNDOWN_FLOOR:
        return
    subprocess.run(["schtasks", "/Delete", "/TN", BURNDOWN_TASK, "/F"],
                   capture_output=True, creationflags=NOWIN)
    notify("✅ Backlog burndown complete - queue at %d. Back to the normal "
           "2 posts/day." % remaining)


def main():
    if "--login" in sys.argv:
        login()
        return
    video, left = next_video()
    if not video:
        print("queue empty")
        stop_burndown_if_done(0)
        return
    cap = caption_for(video)
    if "--dry" in sys.argv:
        print("next:", video, "| queue:", left)
        print("caption:", cap)
        return
    keep_awake(True)      # released in the finally below

    # anti-burst guard: if we already posted very recently (overlapping
    # triggers, manual re-run), skip rather than fire a second time close together
    gap = recent_post_gap()
    if gap < MIN_GAP_SEC:
        print("skipping - last post was %.1f min ago (min gap %.0f min)"
              % (gap / 60, MIN_GAP_SEC / 60))
        return

    try:
        # human-like jitter: don't post on the exact scheduled minute
        if "--now" not in sys.argv:
            d = random.randint(0, MAX_JITTER_SEC)
            print("jitter: sleeping %d s before posting" % d)
            time.sleep(d)
        ok, info = post(os.path.join(VIDEO_DIR, video), cap, private="--private" in sys.argv)
        if ok:
            with open(POSTED, "a", encoding="utf-8") as f:
                f.write(video + "\n")
            stamp_post()
            remaining = left - 1
            notify("\U0001F3AC **Posted to TikTok (public, caption included)** - "
                   "fully automatic. %d left in queue.\n`%s`" % (remaining, video))
            print("POSTED:", video)
            stop_burndown_if_done(remaining)
        else:
            notify("\u26A0\uFE0F TikTok auto-post FAILED for `%s` - will retry next slot. %s"
                   % (video, str(info)[:300]))
            print("FAILED:", info)
            sys.exit(1)
    finally:
        keep_awake(False)   # let the PC go back to sleep (unattended timeout)


if __name__ == "__main__":
    main()
