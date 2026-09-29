"""content_sources.py - what the auto-poster makes videos ABOUT.

The render pipeline only ever reads {"title", "selftext"} out of the cache
file, so a new content type costs nothing downstream: write those two fields
and Remotion/edge-tts handle the rest untouched.

Every source returns the same shape:
    {"url", "id", "title", "selftext", "kind"}

`kind` rides along into the rendered filename so autopost.py can pick hooks
and hashtags that match the format - AITA hooks on a movie-facts video would
read as spam.

ROTATION is an explicit repeating cycle indexed by the run number, so the feed
varies but AITA (the proven earner) still carries most slots.

NOTE ON CLIPS: there is deliberately no movie/TV *clip* source here. TikTok
matches copyrighted film and TV footage and issues strikes for it. "Movie
facts" gives the same audience with none of that risk.
"""
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from html import unescape

USER_AGENT = "tiktok-content-bot:v3.0"
CACHE_FILE = "/tmp/reddit_post.json"

# How the feed is paced. AITA keeps the most slots because it is the format
# with 70 posts of proven performance; the rest break up the monotony so the
# account does not read as a single-note bot.
# movietrivia was dropped 2026-09-29: the "facts that sound fake" videos underperformed, so its two
# slots went back to AITA. fetch_movietrivia() stays available but is no longer scheduled.
ROTATION = [
    "aita", "tifu", "aita",
    "aita", "revenge", "wyr",
    "aita", "malicious", "onthisday",
    "aita", "entitled", "aita",
    "aita", "offmychest", "wyr",
]

# Subreddits behind each Reddit-backed kind. Multiple subs per kind widens the
# pool so a slow week on one does not starve the run.
REDDIT_KINDS = {
    "aita":       ["AmItheAsshole"],
    "tifu":       ["tifu"],
    "revenge":    ["pettyrevenge", "ProRevenge"],
    "malicious":  ["MaliciousCompliance"],
    "entitled":   ["EntitledPeople", "ChoosingBeggars"],
    "offmychest": ["TrueOffMyChest", "confession"],
}


# ───────────────────────── Reddit-backed sources ──────────────────────────
def _strip_html(html):
    text = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _post_id(url):
    m = re.search(r"/comments/([^/]+)", url)
    return m.group(1) if m else ""


# ~700 words is about 205 spoken seconds, which still splits into two parts
# that each clear the 60s floor without becoming a slog.
MAX_STORY_WORDS = 700


def _cap_words(text, limit):
    """Trim to `limit` words, backing up to the last sentence end so a story
    never stops mid-clause."""
    words = text.split()
    if len(words) <= limit:
        return text
    clipped = " ".join(words[:limit])
    cut = max(clipped.rfind(". "), clipped.rfind("! "), clipped.rfind("? "))
    return clipped[:cut + 1] if cut > len(clipped) * 0.5 else clipped


def fetch_reddit(subs, used_ids, offset):
    """Top self-posts across one or more subreddits, oldest filters kept from
    the original AITA fetcher (no UPDATE posts, no mod/meta threads)."""
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    eligible, seen = [], set()
    feeds = []
    for sub in subs:
        feeds += [
            "https://www.reddit.com/r/%s/top/.rss?t=week&limit=100" % sub,
            "https://www.reddit.com/r/%s/top/.rss?t=month&limit=100" % sub,
        ]
    for n, feed in enumerate(feeds):
        # Enough candidates already - stop before spending another request.
        if len(eligible) >= 15:
            break
        # Reddit returns 429 when feeds are pulled back to back. One slot only
        # ever needs a handful of requests, so pausing between them is free
        # insurance against rate-limiting the whole rotation into a fallback.
        if n:
            time.sleep(2)
        try:
            req = urllib.request.Request(feed, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp:
                root = ET.fromstring(resp.read())
        except Exception as e:
            print("feed error %s: %s" % (feed, e), file=sys.stderr)
            continue
        for entry in root.findall("atom:entry", ns):
            t_el = entry.find("atom:title", ns)
            l_el = entry.find("atom:link", ns)
            c_el = entry.find("atom:content", ns)
            if t_el is None or l_el is None:
                continue
            title = (t_el.text or "").strip()
            url = l_el.attrib.get("href", "")
            if not url or "/comments/" not in url:
                continue
            low = title.lower()
            if "[mod]" in low or "welcome to" in low or "[meta]" in low:
                continue
            # follow-up posts reference a story the viewer never saw
            if re.search(r"(?i)\bupdate\b", title) or "open forum" in low:
                continue
            pid = _post_id(url)
            if pid in used_ids or pid in seen:
                continue
            body = _strip_html(c_el.text or "" if c_el is not None else "")
            # long enough to clear TikTok's 60s monetization floor once spoken
            if len(body) < 600:
                continue
            # ...and short enough to stay in the proven range. Subs like TIFU
            # run far longer than AITA; a 900-word post becomes a 4.5 minute
            # video, which splits into two parts nobody finishes.
            body = _cap_words(body, MAX_STORY_WORDS)
            seen.add(pid)
            eligible.append({"url": url, "id": pid, "title": title, "selftext": body})
    if not eligible:
        raise RuntimeError("no eligible posts in %s" % ", ".join(subs))
    return eligible[offset % len(eligible)]


# ─────────────────────── Wikipedia "on this day" ──────────────────────────
def fetch_onthisday(used_ids, offset):
    """Free, keyless, and infinite - a different set every calendar day.
    Several events are stitched into one script because a single line is far
    too short to clear 60 seconds."""
    today = date.today()
    url = ("https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/%02d/%02d"
           % (today.month, today.day))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode())
    events = [e for e in data.get("events", []) if e.get("text") and e.get("year")]
    if len(events) < 4:
        raise RuntimeError("not enough on-this-day events")
    events.sort(key=lambda e: -int(e["year"]))
    # Fill to the word target, not a fixed count - six one-line events only
    # runs about 40 seconds, which would miss the 60s monetization floor.
    target = int(WORDS_PER_SEC * TARGET_SECONDS)
    start = (offset * 3) % len(events)
    parts = ["Here is what actually happened on this day in history."]
    used, i = 10, 0
    while used < target and i < len(events):
        e = events[(start + i) % len(events)]
        line = "In %s. %s." % (e["year"], e["text"].rstrip("."))
        parts.append(line)
        used += len(line.split())
        i += 1
    parts.append("Which one surprised you the most? Tell me below.")
    body = " ".join(parts)
    if len(body.split()) < target * 0.8:
        raise RuntimeError("on-this-day too short (%d words)" % len(body.split()))
    return {"url": "https://local/onthisday/comments/otd%02d%02d/" % (today.month, today.day),
            "id": "otd%02d%02d" % (today.month, today.day),
            "title": "What happened on this day in history",
            "selftext": body}


# ───────────────────────── curated script banks ───────────────────────────
# Movie + TV facts. No footage is ever used - these are narrated over the same
# background clip the Reddit stories use, which keeps it copyright-clean.
MOVIE_FACTS = [
    "The T rex roar in Jurassic Park is a baby elephant, an alligator, and a tiger layered together.",
    "Stallone was so broke writing Rocky that he sold his dog for fifty dollars. After the sale he bought him back for three thousand.",
    "Tom Hanks took no salary for Forrest Gump. He took a share of the profits instead and made around forty million dollars.",
    "Eric Stoltz filmed five weeks as Marty McFly before being replaced by Michael J Fox. Almost none of his footage survives.",
    "The shark in Jaws broke down constantly, so Spielberg hid it. That accident is why the movie is terrifying.",
    "Darth Vader's breathing is just a scuba regulator with a microphone inside it.",
    "Harrison Ford had food poisoning the day of the famous sword fight in Raiders. He suggested shooting the swordsman instead, and they kept it.",
    "The Matrix used one hundred and twenty still cameras fired in sequence to invent bullet time.",
    "Alfred Hitchcock used chocolate syrup for blood in Psycho because it filmed better in black and white.",
    "Viggo Mortensen actually broke two toes kicking that helmet in Lord of the Rings. The scream you hear is real pain.",
    "The cat Marlon Brando holds in The Godfather was a stray he found wandering the studio lot.",
    "Johnny Depp modelled Jack Sparrow on Keith Richards, and Disney executives were convinced he was ruining the film.",
    "Shrek was almost entirely recorded by Chris Farley before he died. Mike Myers re-recorded the whole role.",
    "The snow in The Wizard of Oz was industrial asbestos. Nobody knew any better in nineteen thirty nine.",
    "Steven Spielberg offered E.T. product placement to M and Ms and they turned it down. Reese's Pieces sales jumped sixty five percent.",
    "The rippling water in Jurassic Park was made by running a guitar string under the dashboard.",
    "The blue meth in Breaking Bad is blue rock candy, and the crew ate it constantly between takes.",
    "Steve Carell improvised the no God please no line in The Office, and the cast's reaction is genuine.",
    "Ridley Scott did not tell the full cast what would happen in the chestburster scene. Their horror is real.",
    "Mad Max Fury Road used practical effects for about eighty percent of its stunts. Those are real vehicles at real speed.",
    "Whiplash was shot in only nineteen days, and JK Simmons won an Oscar for it.",
    "Christopher Nolan planted five hundred acres of real corn for Interstellar, then sold the harvest for a profit.",
    "Tom Hanks lost fifty pounds for Cast Away, and production shut down for a full year while he did it.",
    "Heath Ledger locked himself in a hotel room for weeks and kept a diary written as the Joker.",
    "Jim Carrey's Grinch makeup was so unbearable that the production hired a man trained to survive torture to coach him through it.",
    "Bong Joon Ho built the entire Parasite house from scratch. It was never a real home.",
    "Leonardo DiCaprio really ate raw bison liver in The Revenant, and he is a vegetarian.",
    "Ryan Reynolds fought for eleven years to get Deadpool made, and leaked the test footage himself.",
    "Coraline is stop motion. Every second you watch took twenty four individually posed frames.",
    "Game of Thrones left a coffee cup in a scene and it was spotted by millions before they edited it out.",
    "The Friends fountain is not in New York. It was on a Warner Brothers backlot in California.",
    "Anthony Hopkins is on screen for only about sixteen minutes in Silence of the Lambs, and won Best Actor for it.",
    "The Blair Witch Project cost about sixty thousand dollars and made almost two hundred and fifty million.",
    "Robert Downey Junior improvised the I am Iron Man line that ended the first movie.",
    "The dress Marilyn Monroe wore over the subway grate took fourteen takes, and crowds ruined most of the audio.",
    "Pixar nearly lost all of Toy Story Two to an accidental delete command. One employee had a backup at home.",
    "Keanu Reeves gave away most of his Matrix sequel earnings to the special effects and costume teams.",
    "The Shining's stair scene was shot one hundred and twenty seven times, a record Shelley Duvall never wanted.",
    "Titanic's sketch of Rose was drawn by James Cameron himself. Those are his hands on screen.",
    "Samuel L Jackson has appeared in films that have grossed more money than any other actor in history.",
    "Michael Myers wears a Captain Kirk mask spray painted white. The whole thing cost under two dollars.",
    "Sean Connery turned down Gandalf because he said he did not understand the script. It would have paid him around four hundred million.",
    "Hugh Jackman only got Wolverine because Dougray Scott dropped out at the last minute.",
    "In Home Alone the photo of Buzz's girlfriend is a boy in a wig. The crew refused to embarrass a real girl.",
    "Psycho was the first American film to show a toilet flushing on screen, and censors fought it.",
    "The dinosaurs in Jurassic Park are on screen for roughly fifteen minutes in the entire film.",
    "Robin Williams improvised so much for Aladdin that the studio ended up with sixteen hours of recordings.",
    "Elsa was written as the villain of Frozen. They heard Let It Go and rewrote the entire movie.",
    "Bryan Cranston shaved his head for Breaking Bad and strangers kept approaching him about his treatment.",
    "Breaking Bad was rejected by HBO, Showtime, FX and TNT before AMC picked it up.",
    "Nobody says the word zombie in The Walking Dead. In that world the word was never invented.",
    "The Sopranos ended by cutting to black so suddenly that thousands of people thought their cable had broken.",
    "The Friends cast negotiated as a group and ended up earning one million dollars each per episode.",
    "Toy Story was the first fully computer animated feature film ever released.",
    "Spirited Away was the first film not in English to win the Oscar for Best Animated Feature.",
    "Real velociraptors were about the size of a turkey. Jurassic Park scaled them up enormously.",
    "Silence of the Lambs is one of only three films ever to win all five major Academy Awards.",
    "Oliver Reed died during the filming of Gladiator and his remaining scenes were finished with early CGI.",
    "The Crow was completed after Brandon Lee's death using a stunt double and digital compositing.",
    "Ferris Bueller's parade scene used a real parade. Most of that crowd had no idea a film was being shot.",
    "Rocky was filmed in twenty eight days on a budget of about one million dollars.",
    "Paranormal Activity cost around fifteen thousand dollars and made nearly two hundred million.",
    "The Nightmare Before Christmas took three years to animate, one frame at a time.",
    "The Mandalorian replaced green screen with a giant curved LED wall and changed how television is filmed.",
    "The Lion King was treated as Disney's B project. Everyone expected Pocahontas to be the hit.",
    "Arnold wanted to say I will be back. The director insisted on I'll be back, and it became the most quoted line of his career.",
    "Jaws is the film that invented the idea of the summer blockbuster.",
    "Stranger Things used a real actor in a practical Demogorgon suit rather than pure CGI.",
    "James Cameron has directed the highest grossing film in the world three separate times.",
    "Alien's tagline, in space no one can hear you scream, is considered one of the greatest ever written.",
    "Jack Nicholson's here's Johnny in The Shining was improvised and the crew nearly ruined the take laughing.",
    "The Godfather horse head was real, sourced from a dog food plant, and the actor's scream is genuine.",
    "Christopher Nolan refuses to use a mobile phone or email on set.",
    "Peter Jackson shot all three Lord of the Rings films at once over four hundred and thirty eight days.",
]

WOULD_YOU_RATHER = [
    "Would you rather always know when someone is lying, or always get away with lying yourself?",
    "Would you rather have unlimited money but no friends, or unlimited friends but never more than you need?",
    "Would you rather relive the same perfect day forever, or never have a bad day again but never a great one?",
    "Would you rather be able to erase one memory, or recover every memory you have ever lost?",
    "Would you rather everyone hear your thoughts for one day, or never be able to speak again?",
    "Would you rather have the ability to undo one decision, or see the outcome of every choice before you make it?",
    "Would you rather be famous for something you did not do, or be forgotten for something incredible you did?",
    "Would you rather never feel physical pain again, or never feel emotional pain again?",
    "Would you rather know exactly when you will die, or exactly how?",
    "Would you rather your partner read every text you have ever sent, or you read every text they have ever sent?",
    "Would you rather be the smartest person in a room where nobody listens, or average in a room that trusts you completely?",
    "Would you rather win the lottery tomorrow, or find out you have a talent nobody else on earth has?",
    "Would you rather lose the ability to lie, or lose the ability to keep a secret?",
    "Would you rather your best friend betray you once badly, or lie to you gently for the rest of your life?",
    "Would you rather have a job you love that barely pays, or a job you hate that makes you rich?",
    "Would you rather go back ten years with everything you know now, or jump ten years ahead?",
    "Would you rather be alone for five years, or surrounded by people who do not understand you for twenty?",
    "Would you rather forget every movie you have seen, or every song you have heard?",
    "Would you rather never be embarrassed again, or never be nervous again?",
    "Would you rather always say what you are thinking, or never be able to say what you mean?",
    "Would you rather have one wish granted today, or three wishes granted in twenty years?",
    "Would you rather everyone forget your name, or everyone remember your worst moment?",
    "Would you rather be able to talk to animals, or speak every human language?",
    "Would you rather never use the internet again, or never travel further than your own town?",
    "Would you rather have everyone believe a lie about you, or nobody believe the truth?",
    "Would you rather lose every photo you have ever taken, or every message you have ever sent?",
    "Would you rather be given the perfect answer to any one question, or a second chance at any one moment?",
    "Would you rather your parents read your search history, or your boss read your group chats?",
    "Would you rather never sleep again and feel fine, or sleep twelve hours a night forever?",
    "Would you rather always be twenty minutes early, or always have an extra hundred dollars in your pocket?",
    "Would you rather know what everyone really thinks of you, or never wonder about it again?",
    "Would you rather be trapped in your favourite show, or have one character from it follow you around?",
    "Would you rather work four days a week for half the pay, or six days for double?",
    "Would you rather never argue with anyone again, or always win every argument?",
    "Would you rather have a photographic memory, or be able to forget anything you choose?",
    "Would you rather your biggest fear be permanent but harmless, or gone but replaced by a random one?",
    "Would you rather live in a world with no music, or a world with no films?",
    "Would you rather be respected by strangers or adored by the people closest to you?",
    "Would you rather find out you were adopted, or find out you have a sibling nobody told you about?",
    "Would you rather always have to tell the truth, or always be assumed to be lying?",
    "Would you rather have your dream job in a city you hate, or an average job somewhere you love?",
    "Would you rather live one life to two hundred, or five separate lives to forty?",
    "Would you rather get everything you asked for, or everything you actually needed?",
    "Would you rather nobody ever remembers your mistakes, or nobody ever remembers your achievements?",
    "Would you rather be able to pause time for ten minutes a day, or rewind one minute once a week?",
    "Would you rather your phone never ran out of battery, or your car never ran out of fuel?",
    "Would you rather have one true friend for life, or a new great friend every single year?",
    "Would you rather know the day everyone you love dies, or never know when anyone will?",
    "Would you rather be the reason someone succeeded, or the reason someone was happy?",
    "Would you rather never be lied to again, or never be judged again?",
    "Would you rather have your childhood back for a week, or see ten years into your future for an hour?",
    "Would you rather lose your sense of taste, or your sense of smell?",
    "Would you rather everyone speak their mind constantly, or nobody ever say anything difficult?",
    "Would you rather be slightly better at everything, or the best in the world at one thing?",
]


# edge-tts at SPEECH_RATE +40% lands around 3.4 spoken words per second, so a
# script must clear ~250 words to beat TikTok's 60s Creator Rewards floor. The
# whole split/monetization design assumes every upload clears it, so these are
# assembled to a WORD TARGET rather than a fixed item count - otherwise a bank
# of short items silently produces unmonetizable 40-second videos.
WORDS_PER_SEC = 3.4
TARGET_SECONDS = 78


def _bank_video(bank, kind, title, intro, outro, offset,
                target_words=int(WORDS_PER_SEC * TARGET_SECONDS)):
    n = len(bank)
    if not n:
        raise RuntimeError("empty bank for %s" % kind)
    # stride by a number coprime with most bank sizes so consecutive runs pull
    # noticeably different windows instead of sliding by one
    start = (offset * 7) % n
    picked, used, i = [], len(intro.split()) + len(outro.split()), 0
    while used < target_words and i < n:
        item = bank[(start + i) % n]
        picked.append(item)
        used += len(item.split())
        i += 1
    if used < target_words * 0.8:
        raise RuntimeError("bank %s too small to clear 60s (%d words)" % (kind, used))
    body = " ".join([intro] + picked + [outro])
    ident = "%s%d" % (kind, start)
    return {"url": "https://local/%s/comments/%s/" % (kind, ident),
            "id": ident, "title": title, "selftext": body}


def fetch_movietrivia(used_ids, offset):
    return _bank_video(
        MOVIE_FACTS, "movietrivia",
        "Movie facts that sound fake but are completely true",
        "Here are some movie facts that sound completely made up but are true.",
        "Which one did you already know? Drop it below.", offset)


def fetch_wyr(used_ids, offset):
    return _bank_video(
        WOULD_YOU_RATHER, "wyr",
        "Would you rather questions that are impossible to answer",
        "Nobody answers all of these the same way. Pick fast, no thinking.",
        "Comment your answers in order. I want to see who agrees with you.", offset)


# ─────────────────────────────── dispatch ─────────────────────────────────
def pick_kind(offset):
    return ROTATION[offset % len(ROTATION)]


def fetch(kind, used_ids, offset):
    if kind in REDDIT_KINDS:
        item = fetch_reddit(REDDIT_KINDS[kind], used_ids, offset)
    elif kind == "onthisday":
        item = fetch_onthisday(used_ids, offset)
    elif kind == "movietrivia":
        item = fetch_movietrivia(used_ids, offset)
    elif kind == "wyr":
        item = fetch_wyr(used_ids, offset)
    else:
        raise RuntimeError("unknown kind %s" % kind)
    item["kind"] = kind
    return item


def fetch_with_fallback(used_ids, offset):
    """Never let one dead source cost a posting slot: try the scheduled kind,
    then walk the rest of the rotation, and land on AITA as the last resort."""
    order = [pick_kind(offset)]
    order += [k for k in dict.fromkeys(ROTATION) if k not in order]
    if "aita" not in order:
        order.append("aita")
    errors = []
    for kind in order:
        try:
            item = fetch(kind, used_ids, offset)
            if kind != order[0]:
                print("fell back to %s (%s failed)" % (kind, order[0]), file=sys.stderr)
            return item
        except Exception as e:
            errors.append("%s: %s" % (kind, str(e)[:70]))
    raise RuntimeError("every source failed -> " + " | ".join(errors))
