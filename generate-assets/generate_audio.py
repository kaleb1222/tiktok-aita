import asyncio
import re
import time
from pathlib import Path

import edge_tts
from edge_tts.exceptions import NoAudioReceived

# Microsoft neural voices — high quality, no API key needed
VOICE_FEMALE = "en-US-JennyNeural"
VOICE_MALE = "en-US-ChristopherNeural"

MAX_RETRIES = 4
RETRY_DELAY = 2  # seconds between retries


def _clean_for_tts(text: str) -> str:
    # Remove markdown bold/italic
    text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def _synthesize_async(text: str, outfile, voice: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(outfile))


def synthesize_audio(text: str, outfile, gender: str = "female") -> None:
    voice = VOICE_FEMALE if gender.lower().startswith("f") else VOICE_MALE
    text = _clean_for_tts(text)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            asyncio.run(_synthesize_async(text, outfile, voice))
            return
        except NoAudioReceived as e:
            last_error = e
            if attempt < MAX_RETRIES:
                print(f"edge-tts NoAudioReceived (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
        except Exception as e:
            raise

    raise RuntimeError(f"edge-tts failed after {MAX_RETRIES} attempts: {last_error}")
