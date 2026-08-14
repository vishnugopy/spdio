# Desktop Cross-Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Song Splitter as a slim native-window desktop app on macOS, Windows, and Linux that downloads the AI engine once on first launch.

**Architecture:** One process: Flask on localhost plus a `pywebview` window. Heavy wheels (torch, numpy, scipy, librosa, soundfile, imageio-ffmpeg) and `baseline.pth` live in the OS application-support folder after a checksummed first-run download. The user’s system Python is never used.

**Tech Stack:** Python 3.10–3.13, Flask, pywebview, PyInstaller, existing vocal-remover U-Net (`separator.py` + `lib/`), pytest.

## Global Constraints

- Desktop only: macOS, Windows, Linux. No mobile, no public website, no stores.
- Songs stay on the machine. Network is used only for the first-run engine download (and retry).
- Never probe or use the user’s system Python.
- Private runtime is inside the app bundle (PyInstaller). Engine wheels unpack to the OS data root.
- Bind Flask to `127.0.0.1` only. Never `0.0.0.0`.
- Data root: macOS `~/Library/Application Support/SongSplitter/`, Windows `%APPDATA%\SongSplitter\`, Linux `~/.local/share/SongSplitter/`.
- Layout under that root: `engine/ready.json`, `data/jobs.json`, `data/jobs/<id>/`, `logs/app.log`, `models/baseline.pth`.
- Unfrozen (dev) jobs stay in `./data`. If `torch` already imports from the venv, skip the engine download.
- First-run UI is an overlay on existing `index.html`, driven by `GET /api/engine` and `POST /api/engine/retry`. No second template. Uploads ignored until ready.
- File → Open and icon-drop POST bytes to existing `/api/upload`. No second ingest API.
- Finished stems use the OS save dialog. Cancel leaves the job. No silent Downloads write. No browser download bar.
- Remove PWA Install button, power/shutdown overlay, and required service worker from the packaged UI.
- Swift shell (`native/main.swift`) is unused by the release app. Keep `start.command` / `start.bat` / `install_deps.py` for dev.
- PyInstaller onedir, windowed. Exclude torch, numpy, scipy, librosa, soundfile, imageio-ffmpeg, and the model.
- Mac first: Developer ID sign with hardened runtime + `entitlements.plist` (`com.apple.security.cs.disable-library-validation`), notarize, staple, DMG. Windows = unsigned zip of onedir. Linux = AppImage.
- v1 targets: macos-arm64, macos-x64, windows-x64, linux-x64.
- User errors: one actionable sentence. Details in `logs/app.log`. No audio in the log.
- No new splitter features. No visual redesign of the song list or player.
- TDD for new Python modules. Commit after each task.

---

## File structure

| File | Responsibility |
|---|---|
| `app_paths.py` | Frozen detection, OS data root, jobs/engine/models/log paths |
| `audio_sniff.py` | Content-type sniff moved out of `app.py` |
| `engine_bootstrap.py` | Manifest load, platform key, download/verify/extract, ready marker, `sys.path` activate, status |
| `engine_manifest.json` | Pinned wheel + model URLs and SHA-256 per platform |
| `desktop.py` | pywebview window, menus, file dialogs, icon-drop, save dialog, quit |
| `entitlements.plist` | Mac hardened-runtime entitlements |
| `app.py` | Flask API, job queue; uses paths + engine status; starts desktop when not `SONGSPLITTER_NO_WINDOW` |
| `separator.py` | Lazy numpy; model path from `app_paths.models_dir()` |
| `templates/index.html`, `static/app.js`, `static/style.css` | First-run overlay; remove PWA/shutdown |
| `SongSplitter.spec`, `build.sh` | Slim bundle; sign + notarize + DMG |
| `build_windows.ps1`, `build_linux.sh` | Windows zip, Linux AppImage |
| `tests/test_app_paths.py` | Path layout |
| `tests/test_audio_sniff.py` | Sniff fixtures |
| `tests/test_engine_bootstrap.py` | Download / checksum / ready / corrupt |
| `tests/test_jobs.py` | Queue / cancel / retry / delete via Flask test client |

---

### Task 1: Platform data paths

**Files:**
- Create: `app_paths.py`
- Test: `tests/test_app_paths.py`

**Interfaces:**
- Consumes: `sys.platform`, `sys.frozen`, `Path.home()`, `APPDATA`, `XDG_DATA_HOME`
- Produces:
  - `APP_NAME = "SongSplitter"`
  - `is_frozen() -> bool`
  - `install_root() -> Path` — repo root unfrozen; folder containing the exe when frozen
  - `user_root() -> Path` — OS application-support root
  - `jobs_root() -> Path` — `install_root()/data` when unfrozen, else `user_root()/data`
  - `jobs_dir() -> Path` — `jobs_root()/jobs`
  - `jobs_file() -> Path` — `jobs_root()/jobs.json`
  - `engine_dir() -> Path` — `user_root()/engine`
  - `models_dir() -> Path` — `user_root()/models`
  - `log_path() -> Path` — `user_root()/logs/app.log`
  - `ensure_dirs() -> None` — mkdir all of the above parents

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_app_paths.py
from pathlib import Path
import os
import sys

import app_paths


def test_user_root_macos(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert app_paths.user_root() == tmp_path / "Library" / "Application Support" / "SongSplitter"


def test_user_root_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert app_paths.user_root() == tmp_path / "Roaming" / "SongSplitter"


def test_user_root_linux_xdg(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    assert app_paths.user_root() == tmp_path / "share" / "SongSplitter"


def test_jobs_root_unfrozen_is_repo_data(monkeypatch):
    monkeypatch.setattr(app_paths, "is_frozen", lambda: False)
    assert app_paths.jobs_root() == app_paths.install_root() / "data"


def test_jobs_root_frozen_is_user_data(monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(app_paths, "user_root", lambda: tmp_path / "SongSplitter")
    assert app_paths.jobs_root() == tmp_path / "SongSplitter" / "data"


def test_engine_and_models_and_log_live_under_user_root(monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "user_root", lambda: tmp_path / "SongSplitter")
    assert app_paths.engine_dir() == tmp_path / "SongSplitter" / "engine"
    assert app_paths.models_dir() == tmp_path / "SongSplitter" / "models"
    assert app_paths.log_path() == tmp_path / "SongSplitter" / "logs" / "app.log"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_app_paths.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app_paths'` (install pytest first if missing: `./venv/bin/pip install pytest`)

- [ ] **Step 3: Implement `app_paths.py`**

Implement the functions listed in Interfaces. `is_frozen` is `bool(getattr(sys, "frozen", False))`. `install_root` is `Path(sys.executable).resolve().parent` when frozen, else `Path(__file__).resolve().parent`. Windows `user_root` uses `os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))`. Linux uses `XDG_DATA_HOME` or `~/.local/share`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_app_paths.py -v`
Expected: PASS

- [ ] **Step 5: Point `app.py` job storage at `app_paths`**

Replace the frozen/unfrozen `DATA` block in `app.py` with:

```python
import app_paths

app_paths.ensure_dirs()
DATA = app_paths.jobs_root()
JOBS_DIR = app_paths.jobs_dir()
JOBS_FILE = app_paths.jobs_file()
```

Keep Flask, queue, and routes unchanged.

- [ ] **Step 6: Commit**

```bash
git add app_paths.py tests/test_app_paths.py app.py
git commit -m "Add platform data paths for desktop app data."
```

---

### Task 2: Audio sniff module and tests

**Files:**
- Create: `audio_sniff.py`
- Modify: `app.py` (`_is_audio_file` becomes a wrapper or is replaced)
- Test: `tests/test_audio_sniff.py`

**Interfaces:**
- Consumes: file path
- Produces: `is_audio_file(path) -> bool` — same magic-byte rules as current `app.py` `_is_audio_file`

- [ ] **Step 1: Write the failing tests**

Create tiny fixture bytes in `tests/fixtures/` (or inline in the test) for: ID3 MP3, MPEG frame sync (`\xff\xfb`), RIFF/WAVE, fLaC, OggS, empty file, random text.

```python
# tests/test_audio_sniff.py
from pathlib import Path
import audio_sniff


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_id3_mp3(tmp_path):
    assert audio_sniff.is_audio_file(_write(tmp_path, "a.mp3", b"ID3" + b"\x00" * 20))


def test_mpeg_frame_sync(tmp_path):
    assert audio_sniff.is_audio_file(_write(tmp_path, "b.bin", b"\xff\xfb" + b"\x00" * 20))


def test_wav(tmp_path):
    assert audio_sniff.is_audio_file(_write(tmp_path, "c.wav", b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 8))


def test_flac(tmp_path):
    assert audio_sniff.is_audio_file(_write(tmp_path, "d.flac", b"fLaC" + b"\x00" * 12))


def test_ogg(tmp_path):
    assert audio_sniff.is_audio_file(_write(tmp_path, "e.ogg", b"OggS" + b"\x00" * 12))


def test_rejects_empty(tmp_path):
    assert not audio_sniff.is_audio_file(_write(tmp_path, "empty.bin", b""))


def test_rejects_text(tmp_path):
    assert not audio_sniff.is_audio_file(_write(tmp_path, "note.txt", b"this is not audio"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_audio_sniff.py -v`
Expected: FAIL `No module named 'audio_sniff'`

- [ ] **Step 3: Move the existing `_is_audio_file` body into `audio_sniff.is_audio_file`**

Keep the same magic-byte checks (ID3, fLaC, OggS, RIFF/WAVE, FORM/AIFF, ftyp, WMA GUID, MPEG sync, scan for `\xff\xfb` etc.). In `app.py`, `_is_audio_file` calls `audio_sniff.is_audio_file`.

- [ ] **Step 4: Run tests**

Run: `./venv/bin/python -m pytest tests/test_audio_sniff.py tests/test_app_paths.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add audio_sniff.py tests/test_audio_sniff.py app.py
git commit -m "Extract audio content sniff and add tests."
```

---

### Task 3: Engine bootstrap

**Files:**
- Create: `engine_bootstrap.py`, `engine_manifest.json`
- Test: `tests/test_engine_bootstrap.py`

**Interfaces:**
- Consumes: `app_paths.engine_dir()`, `app_paths.models_dir()`, `engine_manifest.json`, optional `urlopen` hook
- Produces:
  - `platform_key() -> str` — one of `macos-arm64`, `macos-x64`, `windows-x64`, `linux-x64`
  - `load_manifest(path=None) -> dict`
  - `ready_path() -> Path` — `engine_dir() / "ready.json"`
  - `is_ready() -> bool` — `ready.json` exists and `version` equals `manifest["engine_version"]`
  - `venv_has_engine() -> bool` — `import torch` and `import librosa` succeed (dev skip)
  - `needs_download() -> bool` — not `is_ready()` and not `venv_has_engine()`
  - `status() -> dict` — `{ready: bool, progress: int, message: str, error: str|None, downloading: bool}`
  - `ensure_engine(opener=None) -> None` — download wheels + model if needed; updates status; raises `EngineError` with a user-facing `str`
  - `retry() -> None` — clears `error`, calls `ensure_engine` on a daemon thread if not already downloading
  - `activate() -> None` — `sys.path.insert(0, str(engine_dir()))` when `is_ready()`
  - `EngineError(Exception)`

Download rules:
- Pick `manifest["platforms"][platform_key()]`.
- Before download, if free disk bytes on `user_root()` < `manifest["min_free_bytes"]`, raise `EngineError` that includes the space needed.
- Each wheel: GET `url` to `engine_dir() / ".tmp" / name`, SHA-256, compare to `sha256`. Mismatch deletes the temp file and raises `EngineError("The download was damaged. Try again.")`.
- Unpack wheel (zip) into `engine_dir()`.
- Model: GET zip URL, verify SHA-256, extract the first `baseline.pth` into `models_dir() / "baseline.pth"`.
- Skip a wheel if a sidecar `engine_dir() / ".checksums" / name.sha256` already matches.
- On any failure, delete the partial temp file for that item. Do not write `ready.json`.
- On success write `ready.json` as `{"version": "<engine_version>"}`.
- Status `message` while working: `"Downloading the audio engine…"` and `progress` 0–100.
- Offline/timeout: `EngineError("Could not download the audio engine. Check your internet and try again.")`.

`engine_manifest.json` shipped in v1 must include all four platform keys. Pins are exact files from PyPI / download.pytorch.org plus the existing vocal-remover zip:

`https://github.com/tsurumeso/vocal-remover/releases/download/v5.1.1/vocal-remover-v5.1.1.zip`

If a real torch/librosa wheel URL is not yet pinned when this task starts, generate them with:

```bash
./venv/bin/pip download --dest /tmp/ss-wheels --no-deps torch numpy scipy librosa soundfile imageio-ffmpeg
# record each file's URL from pip output or https://pypi.org/pypi/<name>/json
# sha256sum each file
```

Include librosa’s runtime dependencies in the wheel list (at least `audioread`, `decorator`, `joblib`, `lazy_loader`, `msgpack`, `pooch`, `soxr`, `numba`, `llvmlite`, `packaging`, `platformdirs`, `typing_extensions`). Use the current venv’s installed versions so dev and packaged first-run match.

- [ ] **Step 1: Write the failing tests** using a local `http.server` or `urllib` stub that serves a tiny fake wheel (a zip containing `hello.py`) and a tiny zip containing `baseline.pth`.

Cover: missing → download → `is_ready()`; checksum mismatch does not write ready; already-ready skips network; `venv_has_engine` short-circuits when imports work (test by injecting a dummy); corrupt `ready.json` / wrong version is not ready.

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

Run: `./venv/bin/python -m pytest tests/test_engine_bootstrap.py -v`

- [ ] **Step 3: Implement `engine_bootstrap.py` and write `engine_manifest.json`**

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add engine_bootstrap.py engine_manifest.json tests/test_engine_bootstrap.py
git commit -m "Add first-run engine download and checksum bootstrap."
```

---

### Task 4: Separator uses engine model path

**Files:**
- Modify: `separator.py`
- Test: `tests/test_separator_paths.py`

**Interfaces:**
- Consumes: `app_paths.models_dir()`, `engine_bootstrap.activate`
- Produces: `MODEL_PATH` resolved at call time via `model_path() -> Path` = `app_paths.models_dir() / "baseline.pth"` (no longer `BASE / "models"` only)

- [ ] **Step 1: Write a failing test** that monkeypatches `app_paths.models_dir` and asserts `separator.model_path()` follows it. Also assert `import separator` does not import `torch` (check `"torch" not in sys.modules` after deleting it first, or inspect `separator` module globals — `numpy` must not be imported at module top).

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Change `separator.py`**

- Remove top-level `import numpy as np`. Import numpy inside functions that need it.
- Replace `MODEL_PATH = MODELS_DIR / "baseline.pth"` with `def model_path(): return app_paths.models_dir() / "baseline.pth"`.
- `ensure_model` writes to `model_path()`.
- `VocalSeparator.load` calls `engine_bootstrap.activate()` then loads from `model_path()`.

Do not change the U-Net math.

- [ ] **Step 4: Run tests including previous**

- [ ] **Step 5: Commit**

```bash
git add separator.py tests/test_separator_paths.py
git commit -m "Load the vocal model from the user engine folder."
```

---

### Task 5: Engine HTTP API, job gate, first-run overlay

**Files:**
- Modify: `app.py`, `templates/index.html`, `static/app.js`, `static/style.css`
- Test: `tests/test_jobs.py`, `tests/test_engine_api.py`

**Interfaces:**
- Consumes: `engine_bootstrap.status`, `ensure_engine`, `retry`, `needs_download`, `is_ready`, `venv_has_engine`
- Produces:
  - `GET /api/engine` → `status()` JSON
  - `POST /api/engine/retry` → starts `retry()`, returns `status()`
  - `POST /api/upload` returns 503 `{error: "The audio engine is still downloading."}` when `needs_download()`
  - Worker calls `engine_bootstrap.activate()` before `separator.load`

- [ ] **Step 1: Write Flask test-client tests**

Use `app.app` with `SONGSPLITTER_NO_WINDOW=1` and `SONGSPLITTER_NO_BROWSER=1`. Monkeypatch `engine_bootstrap.needs_download` / `status` / `retry`.

- `GET /api/engine` returns `ready` / `progress` / `message` / `error` / `downloading`
- `POST /api/upload` is 503 when `needs_download()` is True
- `POST /api/upload` of a tiny ID3 file succeeds when engine is ready (monkeypatch `VocalSeparator.separate` to write `vocals.mp3` and `music.mp3`)
- cancel / retry / delete of a queued or fake-done job work as today

- [ ] **Step 2: Run — expect FAIL (routes missing)**

- [ ] **Step 3: Implement routes and overlay**

`index.html`: add `#engine-overlay` (same visual language as `.drop-overlay`) with message, progress bar, Retry button (`#engine-retry`), hidden when ready.

`app.js`: on load, poll `GET /api/engine` every 500ms until `ready`. Show overlay when not ready. Disable drop/file input while not ready. Retry button POSTs `/api/engine/retry`.

`app.py` `__main__`: if `needs_download()`, start `ensure_engine` on a daemon thread after Flask starts.

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add app.py templates/index.html static/app.js static/style.css tests/test_jobs.py tests/test_engine_api.py
git commit -m "Add engine status API and first-run download overlay."
```

---

### Task 6: Native desktop window

**Files:**
- Create: `desktop.py`
- Modify: `app.py` `__main__`, `requirements.txt`
- Test: `tests/test_desktop_menu.py` (pure functions only — do not require a display)

**Interfaces:**
- Consumes: Flask port, `pywebview`
- Produces:
  - `start_window(port: int) -> None` — blocks on the UI thread
  - `menu_items()` → pywebview menu tree: Song Splitter (About, Quit), File (Open songs…), Window (Minimize, Close), Help (How to use)
  - `ABOUT_TEXT` = `Song Splitter\nVersion 1.0.0\nRuns entirely on this computer.`
  - `HELP_TEXT` = `Drop songs on the window or use File → Open. Vocals and music stay on this computer.`
  - `open_songs(window)` — multi-select audio file dialog; POST each file to `http://127.0.0.1:{port}/api/upload`
  - `save_stem(window, job_id, stream, suggested_name)` — GET `/api/download/...` bytes, OS save dialog, write file; cancel is a no-op
  - Window title `Song Splitter`, size 1024×700, min 720×500, `easy_drag=False`, remember size via pywebview `min_size`

Add `pywebview>=5.0` to `requirements.txt` (keep existing engine deps for the dev venv).

`app.py` `__main__`:
- Always set no-browser when starting the desktop window.
- If env `SONGSPLITTER_NO_WINDOW` is set (tests / headless), keep current Flask-only behavior (and only open a browser if `SONGSPLITTER_NO_BROWSER` is unset — current behavior).
- Otherwise: start Flask in a daemon thread, wait until `GET /api/history` returns 200, then `desktop.start_window(port)`. Last window close exits the process (`os._exit(0)` after joining is fine).

- [ ] **Step 1: Tests for `menu_items` labels and `ABOUT_TEXT` / `HELP_TEXT` exact strings**

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `desktop.py` and wire `__main__`**

Install pywebview in the venv.

- [ ] **Step 4: Manual smoke** (this machine): `SONGSPLITTER_NO_WINDOW=1 ./venv/bin/python app.py` still serves; without the env, a window should open. If the display is unavailable, skip window smoke and note it.

- [ ] **Step 5: Commit**

```bash
git add desktop.py app.py requirements.txt tests/test_desktop_menu.py
git commit -m "Open Song Splitter in a native desktop window."
```

---

### Task 7: Desktop chrome cleanup and save dialog

**Files:**
- Modify: `templates/index.html`, `static/app.js`, `templates/player.html`, `desktop.py`, `app.py`
- Test: `tests/test_desktop_save.py` if save helper is unit-testable; otherwise extend `tests/test_desktop_menu.py`

**Interfaces:**
- Remove `#install-btn`, `#shutdown-btn`, `#shutdown-overlay` from HTML and all JS for PWA / shutdown.
- Stop registering `/sw.js`.
- Keep `/api/shutdown` for now but it is not shown in the UI (dev may still call it).
- Player download `<a href="/api/download/...">` stay as links. In the desktop window, intercept those navigations: `desktop.py` uses pywebview’s events / JS bridge so a click calls `save_stem` with the suggested filename from the link’s `download` attribute.
- File → Open uses the same accept list as the file input: audio extensions in the spec.

- [ ] **Step 1: Grep test or a small HTML parse test is optional; implement then `rg install-btn|shutdown-btn|serviceWorker` and confirm no UI hits**

- [ ] **Step 2: Implement removals + download intercept**

- [ ] **Step 3: Commit**

```bash
git add templates/index.html templates/player.html static/app.js desktop.py app.py
git commit -m "Remove browser chrome and use the OS save dialog."
```

---

### Task 8: Slim packaging, Mac sign/notarize, Windows/Linux scripts

**Files:**
- Create: `entitlements.plist`, `build_windows.ps1`, `build_linux.sh`
- Modify: `SongSplitter.spec`, `build.sh`, `make_icons.py` (add `.ico` / `.png` if missing)
- Test: no pytest; run a slim PyInstaller build on this Mac and confirm torch is not inside the bundle

**Interfaces:**
- Spec excludes: `torch`, `torchvision`, `torchaudio`, `numpy`, `scipy`, `librosa`, `soundfile`, `imageio_ffmpeg`, `numba`, `llvmlite`, `sklearn`
- Datas: `templates`, `static`, `engine_manifest.json` (not `models/`)
- Hidden imports: `app_paths`, `audio_sniff`, `engine_bootstrap`, `desktop`, `lib.*`
- `entitlements.plist`: `com.apple.security.cs.disable-library-validation`, `com.apple.security.network.client`, `com.apple.security.network.server` (localhost)
- `build.sh`: pyinstaller → codesign `--options runtime --entitlements entitlements.plist` → `notarytool submit` if `APPLE_ID` / `APP_PASSWORD` / `TEAM_ID` are set, else print how to notarize → staple when notarized → `ditto` DMG/zip
- `build_windows.ps1`: pyinstaller; zip the onedir folder
- `build_linux.sh`: pyinstaller; optional `appimagetool` if present

- [ ] **Step 1: Update spec and entitlements**

- [ ] **Step 2: Run `./build.sh` on this Mac** (signing uses the Developer ID already detected). Confirm `find dist -iname '*torch*'` is empty.

- [ ] **Step 3: Smoke the slim `.app`**: window opens, first-run overlay appears (engine not bundled). Do not require a full engine download in CI; if network and disk allow, optionally complete first-run and split a short fixture.

- [ ] **Step 4: Commit**

```bash
git add SongSplitter.spec build.sh build_windows.ps1 build_linux.sh entitlements.plist assets/
git commit -m "Package a slim app and sign the Mac build."
```

---

## Self-review

Spec coverage:
- Architecture / one process / localhost → Tasks 5–6
- Slim vs engine download / manifest / checksums / disk / retry → Task 3, 5
- Data locations → Task 1
- Separator model path / lazy imports → Task 4
- First-run overlay / upload gate → Task 5
- Window, menus, File → Open, About → Task 6
- Save dialog, remove PWA/shutdown → Task 7
- Packaging, entitlements, notarize, Win zip, Linux AppImage → Task 8
- Automated sniff / jobs / bootstrap → Tasks 2, 3, 5
- Swift unused, launchers kept → Task 8 leaves them in repo

No TBD left. Names (`needs_download`, `GET /api/engine`, `user_root`) are consistent across tasks.
