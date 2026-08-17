# Spdio

A tiny web app that splits any song into two files:

- **vocals** — just the voice (saved as `first10lettersofsongname_vocal.mp3`)
- **music** — just the instrumental (`first10lettersofsongname_music.mp3`)

It runs entirely on the computer (nothing is uploaded to the internet except the first-time download of the AI model).

## For the person using it

1. Double-click **`start.command`** (Mac) or **`start.bat`** (Windows).
2. The first time, it installs itself automatically — wait a few minutes.
3. Your browser opens the app automatically at `http://127.0.0.1:8080`.
4. Drop one or more songs anywhere on the page (or click the box to browse). They are split one by one.
5. Listen to the **vocals** and **music** previews, then download them whenever you like.

Your songs stay in the list until you delete them, so you can listen again or
re-download at any time. Use **Cancel** to stop a song mid-way, **Retry** to run
a failed or cancelled song again, and the trash button to remove it.

The file type is checked by its actual content, so songs saved with odd names
(like `song.mp3.mpeg`) work fine. Only real audio files are accepted.

## First-time install

You only need Python 3.10–3.13 installed (from python.org). The launcher does everything else: creates a private environment, installs the AI engine (~1.5 GB) and downloads the model (~100 MB).

- **Mac**: right-click `start.command` → Open (the first time only).
- **Windows**: double-click `start.bat`.

Keep the folder where it is — the launcher must stay next to the app files.

## Notes

- Processing happens on your CPU (or Apple GPU via MPS on M-series Macs). A 3-minute song takes roughly 15–60 seconds.
- Only one song is processed at a time; extra uploads wait in line.
- Split files are kept in `data/jobs/` and cleaned up automatically after 6 hours.
- Quality/engine: [vocal-remover](https://github.com/tsurumeso/vocal-remover) (PyTorch), the 2-stems U-Net model.

## Troubleshooting

- **Port 8080 already in use**: quit the other copy of the app first.
- **Install fails**: delete the `venv` folder and run the launcher again.
- **"Python could not be found"**: install Python from https://www.python.org/downloads/ (on Windows, tick *"Add python to PATH"*).
- **Offline first run**: the AI model must be downloaded once. Run it once with internet.

## Publishing the Mac app

The public Mac build must be signed with an Apple **Developer ID Application**
certificate and notarized. The release script refuses to create a distributable
DMG when either requirement is missing, so an unsigned build is not accidentally
published.

Create a local `.env` file with Apple notarization credentials:

```text
APPLE_ID=your-apple-id@example.com
APP_PASSWORD=your-app-specific-password
TEAM_ID=your-team-id
```

Then run:

```bash
./build.sh
```

Publish `dist/Spdio-<version>-macOS-<architecture>.dmg` only after the script completes successfully. The
recipient should be able to drag `Spdio.app` into Applications and open it
without a Gatekeeper warning.
