import os
import shutil
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")


class FFmpegUnavailableError(RuntimeError):
    pass


def _database_path() -> Path:
    configured = os.getenv("SAHAYAK_DB_PATH", "").strip()
    if not configured:
        return BACKEND_ROOT / "sahayak.db"

    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return path.resolve()


DB_PATH = _database_path()


def get_ffmpeg_executable() -> str:
    configured = os.getenv("FFMPEG_PATH", "").strip()
    if configured:
        executable = Path(configured).expanduser()
        if executable.is_dir():
            executable /= "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        if executable.is_file():
            return str(executable)
        raise FFmpegUnavailableError(
            "FFMPEG_PATH does not point to an executable"
        )

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

    raise FFmpegUnavailableError(
        "FFmpeg is unavailable; set FFMPEG_PATH or add it to PATH"
    )
