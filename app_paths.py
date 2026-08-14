import os
import sys
from pathlib import Path

APP_NAME = "SongSplitter"


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def install_root():
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def user_root():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        roaming = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(roaming) / APP_NAME
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def jobs_root():
    if is_frozen():
        return user_root() / "data"
    return install_root() / "data"


def jobs_dir():
    return jobs_root() / "jobs"


def jobs_file():
    return jobs_root() / "jobs.json"


def engine_dir():
    return user_root() / "engine"


def models_dir():
    return user_root() / "models"


def log_path():
    return user_root() / "logs" / "app.log"


def ensure_dirs():
    jobs_dir().mkdir(parents=True, exist_ok=True)
    engine_dir().mkdir(parents=True, exist_ok=True)
    models_dir().mkdir(parents=True, exist_ok=True)
    log_path().parent.mkdir(parents=True, exist_ok=True)
