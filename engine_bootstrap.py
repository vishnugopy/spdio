import hashlib
import json
import os
import shutil
import sys
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import app_paths

ENGINE_VERSION_DEFAULT = "1"
INTERNET_ERROR = "Could not download the audio engine. Check your internet and try again."
DAMAGED_ERROR = "The download was damaged. Try again."


class EngineError(Exception):
    pass


_lock = threading.Lock()
_state = {
    "ready": False,
    "progress": 0,
    "message": "",
    "error": None,
    "downloading": False,
}


def manifest_path():
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "engine_manifest.json"
        if bundled.exists():
            return bundled
    return Path(__file__).resolve().parent / "engine_manifest.json"


def load_manifest(path=None):
    p = Path(path) if path else manifest_path()
    return json.loads(p.read_text())


def platform_key():
    import platform

    mach = platform.machine().lower()
    if sys.platform == "darwin":
        if mach in ("arm64", "aarch64"):
            return "macos-arm64"
        return "macos-x64"
    if sys.platform == "win32":
        return "windows-x64"
    return "linux-x64"


def ready_path():
    return app_paths.engine_dir() / "ready.json"


def is_ready():
    marker = ready_path()
    if not marker.exists():
        return False
    try:
        data = json.loads(marker.read_text())
    except Exception:
        return False
    try:
        expected = str(load_manifest()["engine_version"])
    except Exception:
        expected = ENGINE_VERSION_DEFAULT
    return str(data.get("version")) == expected


def venv_has_engine():
    try:
        import importlib

        importlib.import_module("torch")
        importlib.import_module("librosa")
        return True
    except Exception:
        return False


def needs_download():
    return not is_ready() and not venv_has_engine()


def status():
    with _lock:
        snap = dict(_state)
    snap["ready"] = is_ready() or (not snap["downloading"] and venv_has_engine())
    return snap


def activate():
    if is_ready():
        root = str(app_paths.engine_dir())
        if root not in sys.path:
            sys.path.insert(0, root)


def _set(**fields):
    with _lock:
        _state.update(fields)


def _opener_default(url, timeout=60):
    return urllib.request.urlopen(url, timeout=timeout)


def _readwrite(src, dest, expected_sha):
    h = hashlib.sha256()
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    try:
        with open(part, "wb") as out:
            while True:
                chunk = src.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
    finally:
        if hasattr(src, "close"):
            try:
                src.close()
            except Exception:
                pass
    if h.hexdigest() != expected_sha:
        part.unlink(missing_ok=True)
        raise EngineError(DAMAGED_ERROR)
    part.replace(dest)


def _fetch(url, dest, expected_sha, opener):
    try:
        src = opener(url, timeout=60)
    except EngineError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError):
        raise EngineError(INTERNET_ERROR)
    try:
        _readwrite(src, dest, expected_sha)
    except EngineError:
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        Path(str(dest) + ".part").unlink(missing_ok=True)
        raise EngineError(INTERNET_ERROR)


def _checksum_file(engine, name):
    return engine / ".checksums" / (name + ".sha256")


def _already_have(engine, name, sha256):
    side = _checksum_file(engine, name)
    return side.exists() and side.read_text().strip() == sha256


def _mark_have(engine, name, sha256):
    side = _checksum_file(engine, name)
    side.parent.mkdir(parents=True, exist_ok=True)
    side.write_text(sha256)


def _extract_wheel(wheel_path, dest):
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel_path) as zf:
        zf.extractall(dest)


def _extract_model(zip_path, dest_file):
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.endswith("baseline.pth")]
        if not names:
            raise EngineError(DAMAGED_ERROR)
        with zf.open(names[0]) as src, open(dest_file, "wb") as out:
            shutil.copyfileobj(src, out)


def _check_disk(min_free_bytes):
    root = app_paths.user_root()
    root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(str(root)).free
    if free < int(min_free_bytes):
        gb = int(min_free_bytes) / 1_000_000_000
        raise EngineError(
            "Not enough disk space. About %.0f GB free is needed." % gb
        )


def ensure_engine(opener=None):
    if is_ready():
        _set(ready=True, progress=100, message="", error=None, downloading=False)
        return
    opener = opener or _opener_default
    _set(downloading=True, error=None, message="Downloading the audio engine…", progress=0)
    try:
        manifest = load_manifest()
        key = platform_key()
        platforms = manifest.get("platforms") or {}
        spec = platforms.get(key)
        if not spec:
            raise EngineError("This computer is not supported yet.")
        _check_disk(manifest.get("min_free_bytes") or 0)
        engine = app_paths.engine_dir()
        models = app_paths.models_dir()
        engine.mkdir(parents=True, exist_ok=True)
        models.mkdir(parents=True, exist_ok=True)
        tmp = engine / ".tmp"
        tmp.mkdir(parents=True, exist_ok=True)

        wheels = list(spec.get("wheels") or [])
        items = list(wheels)
        model = spec.get("model")
        total = len(items) + (1 if model else 0)
        done = 0

        for wheel in items:
            name = wheel["name"]
            sha = wheel["sha256"]
            if not _already_have(engine, name, sha):
                dest = tmp / name
                _fetch(wheel["url"], dest, sha, opener)
                _extract_wheel(dest, engine)
                dest.unlink(missing_ok=True)
                _mark_have(engine, name, sha)
            done += 1
            _set(progress=int(done * 100 / total) if total else 100)

        if model:
            name = "model.zip"
            sha = model["sha256"]
            model_out = models / "baseline.pth"
            if not (model_out.exists() and _already_have(engine, name, sha)):
                dest = tmp / name
                _fetch(model["url"], dest, sha, opener)
                _extract_model(dest, model_out)
                dest.unlink(missing_ok=True)
                _mark_have(engine, name, sha)
            done += 1
            _set(progress=int(done * 100 / total) if total else 100)

        ready_path().write_text(
            json.dumps({"version": str(manifest["engine_version"])}, indent=2)
        )
        _set(ready=True, progress=100, message="", error=None, downloading=False)
    except EngineError as exc:
        _set(downloading=False, error=str(exc), message=str(exc))
        raise
    except Exception:
        _set(downloading=False, error=INTERNET_ERROR, message=INTERNET_ERROR)
        raise EngineError(INTERNET_ERROR)


def retry():
    with _lock:
        if _state["downloading"]:
            return
        _state["error"] = None
        _state["downloading"] = True
        _state["message"] = "Downloading the audio engine…"

    def worker():
        try:
            ensure_engine()
        except EngineError:
            pass

    threading.Thread(target=worker, daemon=True).start()
