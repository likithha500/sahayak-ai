
import os
import subprocess
from io import BytesIO

import requests

from .config import FFmpegUnavailableError, get_ffmpeg_executable

GNANI_URL = "https://api.vachana.ai/stt/v3"

SUPPORTED_LANGUAGES = {"kn-IN", "en-IN", "hi-IN"}


class GnaniError(Exception):
    pass


def convert_to_wav(audio_data: bytes) -> bytes:
    """Convert browser audio to 16 kHz mono WAV."""

    if not audio_data:
        raise GnaniError("Audio is empty")

    try:
        ffmpeg = get_ffmpeg_executable()
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-i",
                "pipe:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                "pipe:1",
            ],
            input=audio_data,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except FFmpegUnavailableError as exc:
        raise GnaniError(str(exc)) from exc
    except FileNotFoundError as exc:
        raise GnaniError(
            "Configured FFmpeg executable was not found"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise GnaniError("Audio conversion timed out") from exc

    if result.returncode != 0 or not result.stdout:
        raise GnaniError("Could not convert audio to WAV")

    return result.stdout


def transcribe_audio(
    audio_data: bytes,
    language_codes: str = "kn-IN,en-IN,hi-IN",
) -> dict:
    """Send real audio to Gnani Prisma v3.0."""

    api_key = os.getenv("GNANI_API_KEY", "").strip()

    if not api_key:
        raise GnaniError("GNANI_API_KEY is missing")

    languages = [
        code.strip()
        for code in language_codes.split(",")
    ]

    if (
        not languages
        or len(languages) > 3
        or len(set(languages)) != len(languages)
        or any(
            code not in SUPPORTED_LANGUAGES
            for code in languages
        )
    ):
        raise GnaniError("Unsupported language selection")

    wav_data = convert_to_wav(audio_data)

    try:
        response = requests.post(
            GNANI_URL,
            headers={"X-API-Key-ID": api_key},
            files={
                "audio_file": (
                    "recording.wav",
                    BytesIO(wav_data),
                    "audio/wav",
                )
            },
            data={
                "model": "prisma-v3.0",
                "language_code": ",".join(languages),
                "format": "transcribe",
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        raise GnaniError("Gnani API request failed") from exc

    if not response.ok:
        raise GnaniError(
            f"Gnani returned HTTP {response.status_code}"
        )

    try:
        result = response.json()
    except ValueError as exc:
        raise GnaniError("Gnani returned invalid JSON") from exc

    if result.get("success") is not True:
        raise GnaniError("Gnani transcription failed")

    transcript = result.get("transcript")

    if not isinstance(transcript, str):
        raise GnaniError("Invalid transcript returned")

    return {
        "transcript": transcript,
        "detected_language": result.get(
            "detected_language_code"
        ),
        "model": result.get("model", "prisma-v3.0"),
        "request_id": result.get("request_id"),
        "truncated": bool(result.get("truncated")),
    }
