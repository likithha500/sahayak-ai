
from pathlib import Path
from app.gnani_tts import synthesize_speech

print("Connecting to Gnani Timbre v3.0...")

audio = synthesize_speech(
    text=(
        "Hello! I am Sahayak, your community "
        "health assistant. How can I help you "
        "with today's household visit?"
    ),
    language="en-IN",
)

output = Path(__file__).parent / "sahayak_voice_test.wav"

output.write_bytes(audio)

print("Gnani TTS successful!")
print("Voice: Shivani")
print("Model: timbre-v3.0")
print("Audio size:", len(audio), "bytes")
print("Saved to:", output)
