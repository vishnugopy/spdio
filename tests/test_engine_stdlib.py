import importlib

from engine_stdlib import ENGINE_STDLIB


def test_timeit_is_required():
    assert "timeit" in ENGINE_STDLIB


def test_engine_stdlib_modules_import():
    for name in ENGINE_STDLIB:
        importlib.import_module(name)


def test_spec_bundles_timeit():
    from pathlib import Path

    spec = Path("SongSplitter.spec").read_text()
    assert "ENGINE_STDLIB" in spec or "timeit" in spec
