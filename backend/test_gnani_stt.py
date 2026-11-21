
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

API_KEY = os.getenv("GNANI_API_KEY")

if not API_KEY:
    raise SystemExit("GNANI_API_KEY missing from backend/.env")

if len(sys.argv) < 2:
    raise SystemExit(
        "Usage: python test_gnani_stt.py recording.wav [language]"
    )

audio_path = Path(sys.argv[1])
language = (
    sys.argv[2]
    if len(sys.argv) > 2
    else "kn-IN,en-IN,hi-IN"
)

if not audio_path.is_file():
    raise SystemExit(f"Audio file not found: {audio_path}")

mime_types = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".m4a": "audio/mp4",
}

mime_type = mime_types.get(audio_path.suffix.lower())

if not mime_type:
    raise SystemExit(
        "Unsupported audio format. Use WAV, MP3, OGG, FLAC, AAC or M4A."
    )

print("Sending audio to real Gnani Prisma v3.0...")
print(f"File: {audio_path.name}")
print(f"Language: {language}")

try:
    with audio_path.open("rb") as audio:
        response = requests.post(
            "https://api.vachana.ai/stt/v3",
            headers={"X-API-Key-ID": API_KEY},
            files={
                "audio_file": (
                    audio_path.name,
                    audio,
                    mime_type,
                )
            },
            data={
                "model": "prisma-v3.0",
                "language_code": language,
                "format": "transcribe",
            },
            timeout=60,
        )

    print("HTTP status:", response.status_code)

    if not response.ok:
        print("Gnani error:", response.text[:1500])
        raise SystemExit(1)

    result = response.json()

    if result.get("success") is not True:
        print("Gnani reported an unsuccessful response")
        raise SystemExit(1)

    if result.get("truncated"):
        print("WARNING: Transcript was truncated")

    print("\nTRANSCRIPT:")
    print(result.get("transcript", ""))

    print("\nDetected language:")
    print(result.get("detected_language_code", "Not reported"))

    print("\nModel:")
    print(result.get("model", "Not reported"))

except requests.RequestException as error:
    print("Network/API request failed:", error)
    raise SystemExit(1)
