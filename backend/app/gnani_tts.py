
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"

SUPPORTED_LANGUAGES = {
    "kn-IN",
    "hi-IN",
    "en-IN",
    "auto",
    "hi-en",
}


class GnaniTTSError(Exception):
    pass


def synthesize_speech(
    text: str,
    language: str = "en-IN",
) -> bytes:

    api_key = os.getenv("GNANI_API_KEY", "").strip()

    if not api_key:
        raise GnaniTTSError("GNANI_API_KEY is missing")

    text = text.strip()

    if not text:
        raise GnaniTTSError("Speech text is empty")

    if language not in SUPPORTED_LANGUAGES:
        raise GnaniTTSError("Unsupported language")

    payload = {
        "text": text,
        "voice": "Shivani",
        "model": "timbre-v3.0",
        "language": language,
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 24000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }

    try:
        response = requests.post(
            TTS_URL,
            headers={
                "X-API-Key-ID": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )

    except requests.RequestException as exc:
        raise GnaniTTSError(
            "Gnani TTS connection failed"
        ) from exc

    if response.status_code != 200:
        raise GnaniTTSError(
            f"Gnani TTS returned HTTP {response.status_code}"
        )

    audio = response.content

    if (
        len(audio) < 44
        or audio[:4] != b"RIFF"
        or audio[8:12] != b"WAVE"
    ):
        raise GnaniTTSError(
            "Gnani did not return valid WAV audio"
        )

    return audio
