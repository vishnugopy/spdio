import io
import os

import pytest

os.environ.setdefault("SONGSPLITTER_NO_WINDOW", "1")
os.environ.setdefault("SONGSPLITTER_NO_BROWSER", "1")

import app as appmod


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(appmod, "JOBS_FILE", tmp_path / "jobs.json")
    appmod.JOBS_DIR.mkdir()
    appmod.jobs.clear()
    appmod.queue.clear()
    appmod.app.config["TESTING"] = True
    return appmod.app.test_client()


def test_engine_status(client, monkeypatch):
    monkeypatch.setattr(
        appmod.engine_bootstrap,
        "status",
        lambda: {
            "ready": False,
            "progress": 12,
            "message": "Downloading the audio engine…",
            "error": None,
            "downloading": True,
        },
    )
    res = client.get("/api/engine")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ready"] is False
    assert data["progress"] == 12
    assert data["downloading"] is True


def test_upload_rejected_while_downloading(client, monkeypatch):
    monkeypatch.setattr(appmod.engine_bootstrap, "needs_download", lambda: True)
    res = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(b"ID3" + b"\x00" * 20), "song.mp3")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 503
    assert "engine" in res.get_json()["error"].lower()


def test_upload_ok_when_ready(client, monkeypatch):
    monkeypatch.setattr(appmod.engine_bootstrap, "needs_download", lambda: False)
    res = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(b"ID3" + b"\x00" * 20), "song.mp3")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert res.get_json()["job_id"]


def test_engine_retry(client, monkeypatch):
    called = {"n": 0}

    def fake_retry():
        called["n"] += 1

    monkeypatch.setattr(appmod.engine_bootstrap, "retry", fake_retry)
    monkeypatch.setattr(
        appmod.engine_bootstrap,
        "status",
        lambda: {
            "ready": False,
            "progress": 0,
            "message": "Downloading the audio engine…",
            "error": None,
            "downloading": True,
        },
    )
    res = client.post("/api/engine/retry")
    assert res.status_code == 200
    assert called["n"] == 1
    assert res.get_json()["downloading"] is True
