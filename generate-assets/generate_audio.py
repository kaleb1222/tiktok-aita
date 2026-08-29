import asyncio
import re
import time
from pathlib import Path

# Primary: edge-tts (Microsoft neural voices — much more natural)
# Fallback: gTTS (Google, HTTPS-based, works anywhere including GitHub Actions)

# Multilingual neural voices — noticeably warmer and more conversational than
# the older Jenny/Christopher pair, which read flat for storytime narration.
# Narration speed. 1.25x read a little slow, so 1.4x.
SPEECH_RATE = "+40%"

VOICE_FEMALE = "en-US-AvaMultilingualNeural"
VOICE_MALE = "en-US-AndrewMultilingualNeural"


def _clean_for_tts(text: str) -> str:
    text = re.sub(r"\*+([^*]+)\*+", r"\1", text)   # strip markdown bold/italic
    text = re.sub(r"https?://\S+", "", text)         # remove URLs
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _synthesize_gtts(text: str, outfile) -> None:
    from gtts import gTTS
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(str(outfile))


async def _synthesize_edge_async(text: str, outfile, voice: str):
    """Synthesize and ALSO return per-word timings.

    communicate.save() throws the WordBoundary events away, so stream instead:
    the boundaries are what let the on-screen captions track the narration.
    Offsets are in 100-nanosecond ticks and already account for SPEECH_RATE.
    """
    import edge_tts
    # boundary defaults to SentenceBoundary, which gives no per-word data —
    # ask for WordBoundary explicitly or the captions cannot track the voice.
    communicate = edge_tts.Communicate(text, voice, rate=SPEECH_RATE,
                                       boundary="WordBoundary")
    words = []
    with open(outfile, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "w": chunk["text"],
                    "t": round(chunk["offset"] / 1e7, 3),
                    "d": round(chunk["duration"] / 1e7, 3),
                })
    return words


def synthesize_audio(text: str, outfile, gender: str = "female"):
    voice = VOICE_FEMALE if gender.lower().startswith("f") else VOICE_MALE
    text = _clean_for_tts(text)
    # Skip if there are no actual words (e.g. phrase is just "-" or "," after cleaning)
    if not text or not re.search(r"\w", text):
        print(f"[TTS] Skipping empty/no-word phrase: {repr(text)}")
        return []

    print(f"[TTS] Synthesizing ({len(text)} chars, voice={voice}): {text[:60]!r}...")

    # Try edge-tts first (Microsoft neural — much more natural)
    try:
        return asyncio.run(_synthesize_edge_async(text, outfile, voice))
    except Exception as e:
        print(f"edge-tts failed, falling back to gTTS: {e}")

    # Fallback: gTTS (robotic but reliable everywhere)
    for attempt in range(1, 4):
        try:
            _synthesize_gtts(text, outfile)
            return []   # gTTS gives no word timings; captions fall back to full text
        except Exception as e:
            if attempt < 3:
                print(f"gTTS attempt {attempt}/3 failed: {e}, retrying in 2s...")
                time.sleep(2)
            else:
                raise RuntimeError(f"Both edge-tts and gTTS failed. Last error: {e}")
