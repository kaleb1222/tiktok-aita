import asyncio
import re
import time
from pathlib import Path

# Primary: gTTS (Google, HTTPS-based, works anywhere including GitHub Actions)
# Fallback: edge-tts (Microsoft neural, higher quality, but blocked on some CI runners)

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
    if not text:
        return

    # Try gTTS first (reliable in GitHub Actions)
    for attempt in range(1, 4):
        try:
            _synthesize_gtts(text, outfile)
            return
        except Exception as e:
            if attempt < 3:
                print(f"gTTS attempt {attempt}/3 failed: {e}, retrying in 2s...")
                time.sleep(2)
            else:
                print(f"gTTS failed after 3 attempts, falling back to edge-tts: {e}")

    # Fallback to edge-tts (higher quality, works locally)
    try:
        asyncio.run(_synthesize_edge_async(text, outfile, voice))
    except Exception as e:
        raise RuntimeError(f"Both gTTS and edge-tts failed. Last error: {e}")
