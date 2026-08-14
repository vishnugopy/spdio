from pathlib import Path
import sys

import app_paths


def test_user_root_macos(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert app_paths.user_root() == tmp_path / "Library" / "Application Support" / "Spdio"


def test_user_root_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert app_paths.user_root() == tmp_path / "Roaming" / "Spdio"


def test_user_root_linux_xdg(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    assert app_paths.user_root() == tmp_path / "share" / "Spdio"


def test_jobs_root_unfrozen_is_repo_data(monkeypatch):
    monkeypatch.setattr(app_paths, "is_frozen", lambda: False)
    assert app_paths.jobs_root() == app_paths.install_root() / "data"


def test_jobs_root_frozen_is_user_data(monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(app_paths, "user_root", lambda: tmp_path / "Spdio")
    assert app_paths.jobs_root() == tmp_path / "Spdio" / "data"


def test_engine_and_models_and_log_live_under_user_root(monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "user_root", lambda: tmp_path / "Spdio")
    assert app_paths.engine_dir() == tmp_path / "Spdio" / "engine"
    assert app_paths.models_dir() == tmp_path / "Spdio" / "models"
    assert app_paths.log_path() == tmp_path / "Spdio" / "logs" / "app.log"


def test_migrate_legacy_folder(monkeypatch, tmp_path):
    old = tmp_path / "Library" / "Application Support" / "SongSplitter"
    new = tmp_path / "Library" / "Application Support" / "Spdio"
    old.mkdir(parents=True)
    (old / "engine").mkdir()
    (old / "engine" / "ready.json").write_text("{}")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    app_paths.migrate_legacy_data()
    assert new.exists()
    assert not old.exists()
    assert (new / "engine" / "ready.json").exists()
