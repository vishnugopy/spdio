from pathlib import Path
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
