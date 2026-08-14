import hashlib
import io
import json
import zipfile
from pathlib import Path

import engine_bootstrap


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip_bytes(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _wheel():
    return _zip_bytes({"hello.py": b"print('ok')\n"})


def _model_zip():
    return _zip_bytes({"vocal-remover/models/baseline.pth": b"fake-weights"})


class FakeOpener:
    def __init__(self, files):
        self.files = files
        self.gets = []

    def __call__(self, url, timeout=None):
        self.gets.append(url)
        if url not in self.files:
            raise engine_bootstrap.EngineError("offline")
        return io.BytesIO(self.files[url])


def _manifest(wheel, model, engine_version="1", min_free_bytes=1):
    return {
        "engine_version": engine_version,
        "min_free_bytes": min_free_bytes,
        "platforms": {
            "macos-arm64": {
                "wheels": [
                    {
                        "name": "hello-1.0-py3-none-any.whl",
                        "url": "https://example.test/hello.whl",
                        "sha256": _sha256(wheel),
                    }
                ],
                "model": {
                    "url": "https://example.test/model.zip",
                    "sha256": _sha256(model),
                },
            }
        },
    }


def _setup_dirs(monkeypatch, tmp_path, manifest):
    root = tmp_path / "SongSplitter"
    monkeypatch.setattr(engine_bootstrap.app_paths, "user_root", lambda: root)
    monkeypatch.setattr(engine_bootstrap.app_paths, "engine_dir", lambda: root / "engine")
    monkeypatch.setattr(engine_bootstrap.app_paths, "models_dir", lambda: root / "models")
    monkeypatch.setattr(engine_bootstrap, "platform_key", lambda: "macos-arm64")
    man_path = tmp_path / "engine_manifest.json"
    man_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(engine_bootstrap, "manifest_path", lambda: man_path)
    return root


def test_not_ready_when_missing(monkeypatch, tmp_path):
    wheel, model = _wheel(), _model_zip()
    _setup_dirs(monkeypatch, tmp_path, _manifest(wheel, model))
    assert engine_bootstrap.is_ready() is False


def test_download_writes_ready_and_files(monkeypatch, tmp_path):
    wheel, model = _wheel(), _model_zip()
    root = _setup_dirs(monkeypatch, tmp_path, _manifest(wheel, model))
    opener = FakeOpener(
        {
            "https://example.test/hello.whl": wheel,
            "https://example.test/model.zip": model,
        }
    )
    engine_bootstrap.ensure_engine(opener=opener)
    assert engine_bootstrap.is_ready() is True
    assert (root / "engine" / "hello.py").read_bytes() == b"print('ok')\n"
    assert (root / "models" / "baseline.pth").read_bytes() == b"fake-weights"
    ready = json.loads((root / "engine" / "ready.json").read_text())
    assert ready["version"] == "1"


def test_extract_wheel_restores_ffmpeg_executable_bit(tmp_path):
    wheel = tmp_path / "ffmpeg.whl"
    wheel.write_bytes(_zip_bytes({"imageio_ffmpeg/binaries/ffmpeg-test": b"binary"}))
    dest = tmp_path / "engine"

    engine_bootstrap._extract_wheel(wheel, dest)

    binary = dest / "imageio_ffmpeg" / "binaries" / "ffmpeg-test"
    assert binary.stat().st_mode & 0o111


def test_bad_checksum_does_not_write_ready(monkeypatch, tmp_path):
    wheel, model = _wheel(), _model_zip()
    man = _manifest(wheel, model)
    man["platforms"]["macos-arm64"]["wheels"][0]["sha256"] = "0" * 64
    root = _setup_dirs(monkeypatch, tmp_path, man)
    opener = FakeOpener(
        {
            "https://example.test/hello.whl": wheel,
            "https://example.test/model.zip": model,
        }
    )
    try:
        engine_bootstrap.ensure_engine(opener=opener)
        assert False, "expected EngineError"
    except engine_bootstrap.EngineError as exc:
        assert "damaged" in str(exc).lower()
    assert engine_bootstrap.is_ready() is False
    assert not (root / "engine" / "ready.json").exists()


def test_already_ready_skips_network(monkeypatch, tmp_path):
    wheel, model = _wheel(), _model_zip()
    root = _setup_dirs(monkeypatch, tmp_path, _manifest(wheel, model))
    engine = root / "engine"
    engine.mkdir(parents=True)
    (engine / "ready.json").write_text(json.dumps({"version": "1"}))
    opener = FakeOpener({})
    engine_bootstrap.ensure_engine(opener=opener)
    assert opener.gets == []


def test_wrong_version_is_not_ready(monkeypatch, tmp_path):
    wheel, model = _wheel(), _model_zip()
    root = _setup_dirs(monkeypatch, tmp_path, _manifest(wheel, model, engine_version="2"))
    engine = root / "engine"
    engine.mkdir(parents=True)
    (engine / "ready.json").write_text(json.dumps({"version": "1"}))
    assert engine_bootstrap.is_ready() is False


def test_venv_has_engine_skips_needs_download(monkeypatch):
    monkeypatch.setattr(engine_bootstrap, "is_ready", lambda: False)
    monkeypatch.setattr(engine_bootstrap, "venv_has_engine", lambda: True)
    assert engine_bootstrap.needs_download() is False


def test_activate_inserts_engine_dir(monkeypatch, tmp_path):
    wheel, model = _wheel(), _model_zip()
    root = _setup_dirs(monkeypatch, tmp_path, _manifest(wheel, model))
    engine = root / "engine"
    engine.mkdir(parents=True)
    (engine / "ready.json").write_text(json.dumps({"version": "1"}))
    import sys

    engine_bootstrap.activate()
    assert str(engine) == sys.path[0]
    sys.path.pop(0)


def test_status_shape(monkeypatch, tmp_path):
    wheel, model = _wheel(), _model_zip()
    _setup_dirs(monkeypatch, tmp_path, _manifest(wheel, model))
    monkeypatch.setattr(engine_bootstrap, "venv_has_engine", lambda: False)
    st = engine_bootstrap.status()
    assert set(st) >= {"ready", "progress", "message", "error", "downloading"}
    assert st["ready"] is False
