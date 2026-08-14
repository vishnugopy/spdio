# Song Splitter — desktop cross-platform design

Date: 2026-08-14
Status: approved in conversation; waiting for spec review

## Goal

Ship Song Splitter as a real desktop app on **macOS, Windows, and Linux**.

Users double-click an icon. They do not install Python. They do not open a browser tab. Songs stay on the computer. The first launch downloads the AI engine once; after that the app works offline.

Same splitter features as today (drop songs, queue, preview, download vocals and music). The window, menus, and installers are new.

## Non-goals (v1)

- iPhone, iPad, Android, or a public website
- Mac App Store, Microsoft Store, or Linux distro packages
- Auto-update
- A Windows code-signing certificate
- New splitter features (extra stems, other models, folder watch)
- Visual redesign of the song list or player
- Using Python that happens to be installed on the user’s PC

## Decisions

| Topic | Choice |
|---|---|
| Platforms | macOS, Windows, Linux (desktop only) |
| Distribution | Direct downloads. Mac is Developer ID signed and notarized. Windows and Linux are unsigned in v1. |
| Product | Same features, desktop chrome |
| Shell | `pywebview` + existing Flask UI |
| Engine | Private runtime in the app; heavy libraries downloaded once |
| Mac identity | Developer ID + notarization (Apple Developer account) |

## Architecture

One OS process, two roles inside it.

1. **Window** — `pywebview` native window (WKWebView on Mac, Edge WebView2 on Windows, WebKitGTK on Linux). It loads `http://127.0.0.1:<port>/`.
2. **App server** — the existing Flask app on a background thread. Binds to localhost only. A free port is chosen at startup (current 8080–8089 scan). The browser is never opened.

On launch:

1. Resolve the platform data directory and log file.
2. Start Flask with `SONGSPLITTER_NO_BROWSER=1`.
3. Open the native window on `/`.
4. If the engine is not ready, `index.html` shows a first-run overlay (no second template). `GET /api/engine` reports status and percent. Upload, File → Open, and icon-drop are ignored until ready.
5. Quit (menu or last window close) stops Flask and exits. No leftover process.

The Swift Mac shell (`native/main.swift`) is **not** used in the release app. One wrapper on all three platforms.

`start.command` and `start.bat` remain a **developer** path: run from a source checkout with a local venv. They are not the product users download.

### What is in the slim app vs the engine

**Shipped in the installer** (tens of MB, not a gigabyte):

- Private CPython (PyInstaller), Flask, `pywebview`
- Templates, static UI, icons
- Bootstrapper that can download, verify, and unpack wheels
- `engine_manifest.json` (pinned wheel URLs and checksums)

**Downloaded on first launch** into the data directory:

- PyTorch (CPU wheel on Windows/Linux; default Mac wheel with MPS)
- `numpy`, `scipy`, `librosa`, `soundfile`, `imageio-ffmpeg`
- `baseline.pth` (the vocal-remover U-Net weights)

The app never imports `torch`, `numpy`, `scipy`, `librosa`, or `soundfile` until the engine folder is marked ready. `separator.py` already lazy-imports most of those; remaining top-level imports (including `numpy`) move behind the same gate. After ready, bootstrap inserts `engine/` at the front of `sys.path` and only then may `separator.load()` run.

The private runtime is **inside the app bundle**. The user’s system Python is never probed, never required, and never used.

### Data locations

All writable state lives outside the signed/read-only app:

| Platform | Root |
|---|---|
| macOS | `~/Library/Application Support/SongSplitter/` |
| Windows | `%APPDATA%\SongSplitter\` |
| Linux | `~/.local/share/SongSplitter/` |

Layout:

```
SongSplitter/
  engine/                 # unpacked wheels + ready marker
    ready.json            # {"version": "<engine-version>"}
  data/
    jobs.json
    jobs/<id>/
  logs/
    app.log
  models/
    baseline.pth
```

Dev (unfrozen) default stays `./data` for jobs so existing checkouts keep working. Engine still prefers the OS root when missing from the venv, or uses the venv site-packages if those imports already succeed (skip first-run download).

## Components

| Unit | Role | Depends on |
|---|---|---|
| `desktop` (new) | Create window, menus, file dialogs, icon-drop, quit | `pywebview`, Flask URL |
| `engine_bootstrap` (new) | Detect / download / verify / extract engine; report progress | `engine_manifest.json`, network |
| `app.py` | HTTP API, job queue, history | bootstrap (ready?), `separator` |
| `separator.py` + `lib/` | Vocal / music split | engine packages + model |
| UI (`templates/`, `static/`) | Dropzone, queue, player | Flask API |
| Build scripts | Slim PyInstaller artifact per OS; Mac sign + notarize | Apple Developer ID on Mac |

Each unit has one job. The UI does not download wheels. The bootstrapper does not split audio. The separator does not own the window.

## Data flow

### First launch (engine missing or `ready.json` version ≠ manifest)

1. Window opens on `index.html`. JS calls `GET /api/engine`; if not ready, the overlay shows “Downloading the audio engine…” plus a percent. `POST /api/engine/retry` starts or resumes the download (also kicked off automatically on first ready-check).
2. Bootstrap reads `engine_manifest.json`, picks the row for this OS and CPU (macos-arm64, macos-x64, windows-x64, linux-x64).
3. For each pinned wheel: download to a temp file, verify SHA-256, unpack into `engine/`. Resume by skipping files whose checksum already matches.
4. Download the vocal-remover release zip already used by `separator.ensure_model`, verify SHA-256, extract `baseline.pth` into `models/`.
5. Write `ready.json`. Failed or partial files are deleted. Retry is a button, not a restart of the whole app.
6. Overlay hides; the normal song list is shown.

Not enough disk space is a specific error (include the size needed). Offline / timeout / bad checksum: one sentence + Retry.

If `ready.json` is present but imports fail, treat the engine as corrupt and offer re-download.

### Split a song (engine ready)

Unchanged:

1. User adds files (in-page drop, File → Open, or drop onto the app icon). File → Open and icon-drop are handled by the desktop module, which `POST`s the bytes to the existing `/api/upload`. There is no second ingest API.
2. `POST /api/upload` stores the file, content-sniffs audio, enqueues.
3. One worker at a time: load model → separate → encode MP3s.
4. UI polls status; user previews or downloads vocals / music.
5. Cancel, retry, delete behave as they do today.
6. Quit mid-job: that job is `error` with “The app was closed while this song was still being processed. Use retry to finish it.”

Downloads of finished files use the OS save dialog (`pywebview` file dialog). Cancel leaves the job in history. There is no browser download bar and no silent write to Downloads.

Network after a successful first launch is not required. The only network use in v1 is the first-run engine (and a retry of that download).

## Desktop window

- Title: Song Splitter
- Default size 1024×700, minimum 720×500, frame autosaved
- App icon on dock / taskbar / launcher
- Last window close = quit

**Menus**

- Song Splitter: About, Hide (macOS), Quit
- File: Open songs… (multi-select audio)
- Window: Minimize, Close
- Help: short how-to (local, not a website)

About shows name, version, and that it runs entirely on this computer.

**Removed from the HTML UI**

- PWA Install button
- Power / shutdown button and “close this tab” overlay
- Service worker as a required path (`sw.js` / install prompt unused in the packaged app)

In-page drag-and-drop stays. Icon-drop and File → Open are additional ways to hit the same upload API.

## Packaging and signing

Users get three artifacts. No Python install.

| Platform | Artifact | Open |
|---|---|---|
| macOS | Notarized `.dmg` with `SongSplitter.app` | Drag to Applications |
| Windows | Zip of the onedir folder (`SongSplitter.exe` + `_internal`) for x64 | Unzip, double-click the exe |
| Linux | AppImage (x64) | chmod +x, double-click |

PyInstaller **onedir**, windowed (no console). Spec **excludes** torch, numpy, scipy, librosa, soundfile, imageio-ffmpeg, and the model. Includes UI assets and `engine_manifest.json`.

Ship order: **macOS first** (this machine and the Apple account), then Windows, then Linux. One spec; three artifacts.

Icons: existing `assets/AppIcon.icns` for Mac; generate `.ico` and `.png` from the same art for Windows and Linux.

**macOS signing** (Apple Developer account, not Mac App Store):

1. Developer ID Application certificate
2. `codesign --force --deep --options runtime --entitlements entitlements.plist` the `.app`
3. Notarize with `notarytool`
4. Staple the ticket to the app and the `.dmg`

`entitlements.plist` must allow loading the engine’s native libraries from Application Support (`com.apple.security.cs.disable-library-validation`). Hardened runtime without that entitlement will crash on `import torch`. Also allow outgoing network (first-run download) and localhost bind.

Signing without notarization is not enough; Gatekeeper will still block downloaded apps.

**Windows:** unsigned in v1. SmartScreen may warn once. If WebView2 is missing (rare on Windows 10/11), show a message with Microsoft’s WebView2 Evergreen link.

**Linux:** document WebKitGTK as a system package if the AppImage cannot fully bundle it.

Build on the target OS: Mac artifact on a Mac, Windows on Windows, Linux on Linux.

### Engine manifest

`engine_manifest.json` is the only place versions and URLs live. Example shape:

```json
{
  "engine_version": "1",
  "min_free_bytes": 3000000000,
  "platforms": {
    "macos-arm64": {
      "wheels": [
        { "name": "torch", "url": "https://...", "sha256": "..." }
      ],
      "model": { "url": "https://...", "sha256": "..." }
    }
  }
}
```

Wheels come from official indexes (PyPI / `download.pytorch.org`), not a copy we host. Pins are exact files, not “latest”. The wheel list is the **full import closure** needed to run one split (librosa’s dependencies included), not only the top-level names. The `"https://..."` values above are the shape; implementation fills real URLs and SHA-256 hashes. The model entry is the existing vocal-remover GitHub zip plus its checksum.

Supported v1 targets: **macos-arm64**, **macos-x64**, **windows-x64**, **linux-x64**. No Windows ARM, no Linux ARM in v1.

## Errors

User-facing text is one actionable sentence. No stack traces in dialogs. Details go to `logs/app.log` (no audio, no full song paths beyond the original file name).

| Situation | Behaviour |
|---|---|
| Offline / timeout / bad checksum on first run | Message + Retry; window stays up |
| Disk full | Message includes space needed |
| Partial download | Delete temp; next Retry starts clean for that file |
| Engine folder corrupt later | Offer re-download |
| Split fails | That row is error; Retry; queue continues |
| Cancel / delete mid-job | Stop worker for that id; remove temp files |
| Quit mid-job | Job error as today; Retry after reopen |
| Engine import crash after ready | “The audio engine stopped. Reopen the app.” |
| Missing WebView2 | Link to Microsoft installer |
| No free localhost port | Error; do not bind to `0.0.0.0` |

## Testing

### Release checklist (run on each OS)

- Cold start: window opens, UI loads, no browser tab, no console window
- First-run download: progress, files in the OS data dir, second launch skips download
- First-run offline: error + Retry succeeds after network is back
- Split one real song: both stems play and save via the OS save flow
- Queue two songs: serial processing
- Cancel and delete mid-job: worker not stuck; files gone
- Quit during a job: marked failed; Retry works after reopen
- Drop on the page, File → Open, and (macOS/Windows) drop on the app icon
- Quit from menu and by closing the window: no leftover process
- macOS: notarized `.dmg` opens without a Gatekeeper block
- Windows: exe starts; SmartScreen warning acceptable
- Linux: AppImage starts

### Automated (no UI)

- Audio content-type sniff
- Job create / queue / cancel / retry / delete
- Bootstrap: missing, corrupt, already-ready, checksum mismatch
- Dev mode: existing venv with torch does not download

### Out of scope

- Pixel UI tests, store review, Windows Authenticode, auto-update

## File-level plan (implementation, not done in this spec)

New: `desktop.py`, `engine_bootstrap.py`, `engine_manifest.json`, `entitlements.plist`, Windows/Linux icons, Windows/Linux build scripts, first-run overlay in the existing `index.html`.

Change: `app.py` (data paths, no browser, start window, no shutdown-as-product), `separator.py` (engine path + lazy numpy), HTML/JS (remove PWA/shutdown chrome, first-run screen), `SongSplitter.spec` (slim excludes), `build.sh` (sign + notarize + dmg).

Leave in repo but unused by release: `native/main.swift`.

Keep for dev: `start.command`, `start.bat`, `install_deps.py`.

## Success

A person with no Python can download the Mac, Windows, or Linux build, open it, wait through one engine download, drop a song, and take vocals and music home. The Mac build is notarized. Songs never leave the machine except that first-run engine download from official package URLs.
