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
    monkeypatch.setattr(appmod.engine_bootstrap, "needs_download", lambda: False)
    appmod.app.config["TESTING"] = True
    return appmod.app.test_client()


def _upload(client, name="song.mp3"):
    return client.post(
        "/api/upload",
        data={"file": (io.BytesIO(b"ID3" + b"\x00" * 20), name)},
        content_type="multipart/form-data",
    )


def test_cancel_queued_job(client):
    job_id = _upload(client).get_json()["job_id"]
    res = client.post("/api/jobs/%s/cancel" % job_id)
    assert res.status_code == 200
    assert appmod.jobs[job_id]["cancel_requested"] is True


def test_retry_cancelled_job(client):
    job_id = _upload(client).get_json()["job_id"]
    appmod.jobs[job_id]["status"] = "cancelled"
    res = client.post("/api/jobs/%s/retry" % job_id)
    assert res.status_code == 200
    assert appmod.jobs[job_id]["status"] == "queued"


def test_delete_job(client):
    job_id = _upload(client).get_json()["job_id"]
    appmod.jobs[job_id]["status"] = "done"
    res = client.delete("/api/jobs/%s" % job_id)
    assert res.status_code == 200
    assert job_id not in appmod.jobs
