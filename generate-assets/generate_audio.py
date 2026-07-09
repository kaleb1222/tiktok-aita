import asyncio
import re
import time
from pathlib import Path

# Primary: edge-tts (Microsoft neural voices — much more natural)
# Fallback: gTTS (Google, HTTPS-based, works anywhere including GitHub Actions)

VOICE_FEMALE = "en-US-JennyNeural"
VOICE_MALE = "en-US-ChristopherNeural"


def _clean_for_tts(text: str) -> str:
    text = re.sub(r"\*+([^*]+)\*+", r"\1", text)   # strip markdown bold/italic
    text = re.sub(r"https?://\S+", "", text)         # remove URLs
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _synthesize_gtts(text: str, outfile) -> None:
    from gtts import gTTS
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(str(outfile))


async def _synthesize_edge_async(text: str, outfile, voice: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(outfile))


def synthesize_audio(text: str, outfile, gender: str = "female") -> None:
    voice = VOICE_FEMALE if gender.lower().startswith("f") else VOICE_MALE
    text = _clean_for_tts(text)
    # Skip if there are no actual words (e.g. phrase is just "-" or "," after cleaning)
    if not text or not re.search(r"\w", text):
        print(f"[TTS] Skipping empty/no-word phrase: {repr(text)}")
        return

    print(f"[TTS] Synthesizing ({len(text)} chars, voice={voice}): {text[:60]!r}...")

    # Try edge-tts first (Microsoft neural — much more natural)
    try:
        asyncio.run(_synthesize_edge_async(text, outfile, voice))
        return
    except Exception as e:
        print(f"edge-tts failed, falling back to gTTS: {e}")

    # Fallback: gTTS (robotic but reliable everywhere)
    for attempt in range(1, 4):
        try:
            _synthesize_gtts(text, outfile)
            return
        except Exception as e:
            if attempt < 3:
                print(f"gTTS attempt {attempt}/3 failed: {e}, retrying in 2s...")
                time.sleep(2)
            else:
                raise RuntimeError(f"Both edge-tts and gTTS failed. Last error: {e}")
