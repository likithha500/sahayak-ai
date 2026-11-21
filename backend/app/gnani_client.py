
import os
import shutil
import subprocess
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

GNANI_URL = "https://api.vachana.ai/stt/v3"

SUPPORTED_LANGUAGES = {"kn-IN", "en-IN", "hi-IN"}


class GnaniError(Exception):
    pass


def _ffmpeg_executable() -> str:
    configured_path = os.getenv("FFMPEG_PATH", "").strip()
    if configured_path:
        executable = Path(configured_path).expanduser()
        if executable.is_dir():
            executable /= "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        if executable.is_file():
            return str(executable)
        raise GnaniError("FFMPEG_PATH does not point to an executable")

    executable = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if executable:
        return executable

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        package_root = (
            Path(local_app_data)
            / "Microsoft"
            / "WinGet"
            / "Packages"
            / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        )
        candidates = sorted(
            package_root.glob("ffmpeg-*/bin/ffmpeg.exe"),
            reverse=True,
        )
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)

    raise GnaniError("FFmpeg is not installed or not on PATH")


def convert_to_wav(audio_data: bytes) -> bytes:
    """Convert browser audio to 16 kHz mono WAV."""

    if not audio_data:
        raise GnaniError("Audio is empty")

    try:
        result = subprocess.run(
            [
                _ffmpeg_executable(),
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
    except FileNotFoundError as exc:
        raise GnaniError("FFmpeg is not installed") from exc
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
