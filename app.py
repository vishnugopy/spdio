import json
import os
import shutil
import signal
import sys
import threading
import time
import uuid
import webbrowser
from collections import deque
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_file,
    send_from_directory,
)

import app_paths
import audio_sniff
from separator import VocalSeparator

app_paths.ensure_dirs()
DATA = app_paths.jobs_root()
JOBS_DIR = app_paths.jobs_dir()
JOBS_FILE = app_paths.jobs_file()

MAX_UPLOAD = 500 * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD

jobs = {}
jobs_lock = threading.Lock()
queue = deque()
queue_cond = threading.Condition(jobs_lock)
separator = VocalSeparator()

DATA.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)


def _stem10(original_name):
    cleaned = "".join(ch for ch in Path(original_name).stem.lower() if ch.isalnum())
    return cleaned[:10] or "audio"


def _download_names(original_name):
    stem = _stem10(original_name)
    return f"{stem}_vocal.mp3", f"{stem}_music.mp3"


def _is_audio_file(path):
    return audio_sniff.is_audio_file(path)


# ---------------------------------------------------------------- storage
def _save_jobs():
    with jobs_lock:
        snapshot = {k: v for k, v in jobs.items()}
    tmp = JOBS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, indent=2))
    tmp.replace(JOBS_FILE)


def _load_jobs():
    if not JOBS_FILE.exists():
        return
    try:
        data = json.loads(JOBS_FILE.read_text())
    except Exception:
        data = {}
    for jid, j in data.items():
        if not isinstance(j, dict):
            continue
        if j.get("status") not in ("done", "error", "cancelled"):
            j["status"] = "error"
            j["error"] = (
                "The app was closed while this song was still being processed. "
                "Use retry to finish it."
            )
            j["progress"] = 0
        jobs[jid] = j
    _save_jobs()


def _remove_job(job_id):
    with jobs_lock:
        jobs.pop(job_id, None)
    shutil.rmtree(JOBS_DIR / job_id, ignore_errors=True)
    _save_jobs()


# ------------------------------------------------------------------ queue
def _enqueue(job_id):
    with queue_cond:
        queue.append(job_id)
        queue_cond.notify()


def _job(job_id):
    with jobs_lock:
        return jobs.get(job_id)


def _set_job(job_id, persist=True, **fields):
    with jobs_lock:
        j = jobs.get(job_id)
        if j:
            j.update(fields)
    if persist:
        _save_jobs()


class _Cancelled(Exception):
    pass


def _run_job(job_id):
    j = _job(job_id)
    if not j:
        return

    def check_stopped():
        j = _job(job_id)
        if j.get("delete_requested"):
            raise _Cancelled("delete")
        if j.get("cancel_requested"):
            raise _Cancelled("cancel")

    def progress(p):
        check_stopped()
        if isinstance(p, float):
            _set_job(job_id, persist=False, progress=int(p * 100))
        elif isinstance(p, str):
            _set_job(job_id, persist=False, message=p)

    try:
        check_stopped()
        _set_job(job_id, status="loading", message="Preparing the AI model...", progress=0)
        separator.load(progress_cb=progress)
        check_stopped()
        _set_job(job_id, status="working", message="Separating vocals...", progress=2)
        job_dir = JOBS_DIR / job_id
        separator.separate(
            job_dir / j["input_name"], job_dir, progress_cb=progress, check_cancel=check_stopped
        )
        check_stopped()
        vocal_name, music_name = _download_names(j["original_name"])
        _set_job(
            job_id,
            status="done",
            message="Ready",
            progress=100,
            error=None,
            vocal_name=vocal_name,
            music_name=music_name,
        )
    except _Cancelled as exc:
        if exc.args and exc.args[0] == "delete":
            _remove_job(job_id)
        else:
            _set_job(
                job_id,
                status="cancelled",
                message="Cancelled",
                progress=0,
                error=None,
            )
    except Exception as exc:
        app.logger.exception("Job %s failed", job_id)
        _set_job(job_id, status="error", error=str(exc))


def _worker_loop():
    while True:
        to_remove = []
        job_id = None
        with queue_cond:
            while not queue:
                queue_cond.wait()
            while queue:
                jid = queue[0]
                j = jobs.get(jid)
                if j and not j.get("delete_requested"):
                    job_id = queue.popleft()
                    break
                queue.popleft()
                if j:
                    to_remove.append(jid)
        for jid in to_remove:
            _remove_job(jid)
        if job_id:
            _run_job(job_id)


# ---------------------------------------------------------------- routes
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/player/<job_id>")
def player(job_id):
    with jobs_lock:
        j = jobs.get(job_id)
        if not j or j["status"] != "done":
            abort(404)
    vocal_name, music_name = _download_names(j["original_name"])
    return render_template("player.html", job=j, vocal_name=vocal_name, music_name=music_name)


@app.get("/sw.js")
def service_worker():
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


@app.get("/manifest.webmanifest")
def manifest():
    return send_from_directory(
        app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json"
    )


@app.post("/api/upload")
def upload():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="No file selected."), 400
    job_id = uuid.uuid4().hex[:8]
    ext = Path(file.filename).suffix.lower()
    input_name = "input" + (ext or ".bin")
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = job_dir / input_name
    file.save(str(input_path))
    if not _is_audio_file(input_path):
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify(
            error="That doesn't look like an audio file. Please choose a song (MP3, MPEG, WAV, M4A, OGG or FLAC)."
        ), 400
    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "original_name": file.filename,
            "input_name": input_name,
            "status": "queued",
            "progress": 0,
            "message": "Waiting in queue",
            "error": None,
            "vocal_name": None,
            "music_name": None,
            "created_at": time.time(),
            "delete_requested": False,
            "cancel_requested": False,
        }
    _save_jobs()
    _enqueue(job_id)
    return jsonify(job_id=job_id)


@app.get("/api/history")
def history():
    with jobs_lock:
        items = [dict(j) for j in jobs.values()]
    items.sort(key=lambda j: j.get("created_at", 0))
    for j in items:
        if j.get("status") == "done":
            if not j.get("vocal_name"):
                j["vocal_name"], j["music_name"] = _download_names(j["original_name"])
    return jsonify(jobs=items)


@app.get("/api/status/<job_id>")
def status(job_id):
    with jobs_lock:
        j = jobs.get(job_id)
        if not j:
            return jsonify(error="Unknown job."), 404
        return jsonify(**j)


@app.post("/api/jobs/<job_id>/retry")
def retry_job(job_id):
    with jobs_lock:
        j = jobs.get(job_id)
        if not j:
            return jsonify(error="Unknown job."), 404
        if j["status"] in ("queued", "loading", "working"):
            return jsonify(error="Already in progress."), 400
        j.update(
            status="queued",
            message="Waiting in queue",
            error=None,
            progress=0,
            delete_requested=False,
            cancel_requested=False,
        )
    _save_jobs()
    _enqueue(job_id)
    return jsonify(ok=True)


@app.post("/api/jobs/<job_id>/cancel")
def cancel_job(job_id):
    with jobs_lock:
        j = jobs.get(job_id)
        if not j:
            return jsonify(error="Unknown job."), 404
        if j["status"] not in ("queued", "loading", "working"):
            return jsonify(error="Nothing to cancel."), 400
        j["cancel_requested"] = True
    _save_jobs()
    return jsonify(ok=True)


def _force_exit():
    time.sleep(1)
    os._exit(0)


@app.post("/api/shutdown")
def shutdown():
    stop = request.environ.get("werkzeug.server.shutdown")
    if stop:
        stop()
    threading.Thread(target=_force_exit, daemon=True).start()
    return jsonify(ok=True)


@app.delete("/api/jobs/<job_id>")
def delete_job(job_id):
    with jobs_lock:
        j = jobs.get(job_id)
        if not j:
            return jsonify(error="Unknown job."), 404
        j["delete_requested"] = True
        active = j["status"] in ("queued", "loading", "working")
    _save_jobs()
    if not active:
        _remove_job(job_id)
    return jsonify(ok=True)


@app.get("/api/download/<job_id>/<stream>")
def download(job_id, stream):
    if stream not in ("vocals", "music"):
        abort(404)
    with jobs_lock:
        j = jobs.get(job_id)
        if not j:
            abort(404)
    path = _job_output(job_id, stream)
    if not path:
        abort(404)
    vocal_name, music_name = _download_names(j["original_name"])
    download_name = vocal_name if stream == "vocals" else music_name
    return send_file(path, as_attachment=True, download_name=download_name)


@app.get("/api/preview/<job_id>/<stream>")
def preview(job_id, stream):
    if stream not in ("vocals", "music"):
        abort(404)
    with jobs_lock:
        j = jobs.get(job_id)
        if not j or j["status"] != "done":
            abort(404)
    path = _job_output(job_id, stream)
    if not path:
        abort(404)
    return send_file(path, conditional=True)


def _job_output(job_id, stream):
    name = "vocals.mp3" if stream == "vocals" else "music.mp3"
    path = JOBS_DIR / job_id / name
    return path if path.exists() else None


def _find_free_port():
    import socket

    for port in range(8080, 8090):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    return 8080


def _open_browser(port):
    time.sleep(1.5)
    try:
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception:
        pass


def _handle_sigterm(signum, frame):
    """Exit quickly and cleanly when the app shell terminates us."""
    threading.Thread(target=_force_exit, daemon=True).start()


if __name__ == "__main__":
    _load_jobs()
    threading.Thread(target=_worker_loop, daemon=True).start()
    port = int(os.environ.get("PORT", "0")) or _find_free_port()
    if not os.environ.get("SONGSPLITTER_NO_BROWSER"):
        threading.Thread(target=_open_browser, args=(port,), daemon=True).start()
    signal.signal(signal.SIGTERM, _handle_sigterm)
    app.run(host="127.0.0.1", port=port, threaded=True)
