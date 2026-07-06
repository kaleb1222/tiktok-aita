import asyncio
from pathlib import Path

import edge_tts

# Microsoft neural voices — high quality, no API key needed
VOICE_FEMALE = "en-US-JennyNeural"
VOICE_MALE = "en-US-ChristopherNeural"


async def _synthesize_async(text: str, outfile, voice: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(outfile))


def synthesize_audio(text: str, outfile, gender: str = "female") -> None:
    voice = VOICE_FEMALE if gender.lower().startswith("f") else VOICE_MALE
    asyncio.run(_synthesize_async(text, outfile, voice))
