import json
import re
import readline
import sys
import urllib.request
from html import unescape
from pathlib import Path

from mutagen.mp3 import MP3

from clean_up_text import clean_up_text, find_gender, split_and_correct_text
from emoji_suggester import neutral_emoji, suggest_emoji
from generate_audio import synthesize_audio

user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'


def pinput(prompt, text):
    def hook():
        readline.insert_text(text)
        readline.redisplay()
    readline.set_pre_input_hook(hook)
    result = input(prompt)
    readline.set_pre_input_hook()
    return result


CACHE_FILE = "/tmp/reddit_post.json"


def get_post(url):
    # Use cached data written by fetch_top_post.py to avoid a second Reddit request
    # (GitHub Actions IPs are blocked by Reddit's .json endpoint)
    import os
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            data = json.load(f)
        selftext = unescape(clean_up_text(data["selftext"]))
        title = clean_up_text(data["title"].replace('"', ""))
        return (selftext, title)

    # Fallback: direct fetch (works locally, blocked on GH Actions)
    request = urllib.request.Request(
        url=url.rstrip("/") + ".json",
        data=None,
        headers={'User-Agent': user_agent}
    )
    with urllib.request.urlopen(request) as resp:
        json_data = json.loads(resp.read().decode())

    data = json_data[0]["data"]["children"][0]["data"]
    selftext = unescape(clean_up_text(data["selftext"]))
    title = clean_up_text(data["title"].replace('"', ""))
    return (selftext, title)


def main(post_url):
    print()
    print(post_url)

    workspace = Path.joinpath(Path("workspace"), Path(post_url.split("/")[-2]))
    audio_root = workspace.joinpath("sounds/")
    audio_root.mkdir(parents=True, exist_ok=True)

    (selftext, title) = get_post(post_url)
    selftext = re.sub(r"\.", ". ", selftext)
    selftext = re.sub(r"\bsubmitted by\b.*", "", selftext, flags=re.IGNORECASE).strip()
    selftext = selftext.replace("reddit", "TikTok")
    selftext = selftext + " - What do you think? Doubletap and comment your opinion."
    selftext = selftext.replace("&", " and ")

    print()
    print(title)
    print()

    gender = "male"
    print(f"Gender: {gender}")

    phrases = []

    for (i, phrase) in enumerate(split_and_correct_text(selftext)):
        # if i == 3:
        #     break
        if not phrase or not re.search(r'\w', phrase):
            continue
        phrases.append(phrase)

    final_script = []
    i = 0
    for phrase in phrases:
        audio_out = audio_root.joinpath(f"sound-{i}.mp3")

        skip_regen = False
        if not skip_regen or not audio_out.exists():
            synthesize_audio(
                text=phrase,
                outfile=audio_out,
                gender=gender
            )

        if len(phrase.split()) < 35:
            emoji = suggest_emoji(phrase)
            if not emoji and i > 3 and i < len(phrases)-2:
                emoji = neutral_emoji(len(phrase))
        else:
            emoji = ""

        audio = MP3(audio_out)
        info = {
            "text": phrase,
            "emoji": emoji,
            "duration": audio.info.length,
            "audio_file": audio_out.name
        }
        final_script.append(info)
        i = i+1

    final_title = clean_up_text(title)

    # ── Build a TikTok-SEO title + filename from this specific story ──────────
    seo_hashtags = ("#redditstories #aita #storytime #reddit "
                    "#amitheasshole #redditreadings #fyp #redditstorytime")
    hook = final_title.rstrip(" ?.!")
    if not re.match(r"(?i)\s*(aita\b|am i the)", hook):
        hook = f"AITA {hook}"
    # Readable caption (goes in script.json as seo_title for the TikTok post)
    seo_title = f"{hook}? \U0001F62E | Reddit AITA Story {seo_hashtags}"

    # SEO filename: keyword-front-loaded, readable, filesystem-safe, length-capped
    slug_words = re.sub(r"[^a-zA-Z0-9]+", " ", final_title).split()
    slug = "_".join(slug_words[:12])
    slug = slug[:90].strip("_")
    if not re.match(r"(?i)aita", slug):
        slug = f"AITA_{slug}"
    filename = re.sub(r"_+", "_", f"{slug}_Reddit_Story_Storytime").strip("_")

    audio_out = audio_root.joinpath("title.mp3")
    synthesize_audio(
        text=final_title,
        outfile=audio_out,
        gender=gender
    )
    audio = MP3(audio_out)

    emoji = suggest_emoji(final_title) or ""
    if not emoji:
        emoji = "man-shrugging" if gender.startswith(
            "m") else "woman-shrugging"

    info = {
        "filename": f"{filename}.mp4",
        "seo_title": seo_title,
        "text": final_title,
        "emoji": emoji,
        "duration": audio.info.length,
        "audio_file": audio_out.name
    }

    result = {
        "workdir": str(workspace),
        "url": post_url,
        "title": info,
        "script": final_script
    }

    info_out = workspace.joinpath("script.json")
    with open(info_out, 'w') as f:
        json.dump(result, f, indent=4, sort_keys=True)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        post = input("Enter reddit URL: ")
    else:
        post = sys.argv[1]

    main(post)
