import ast
import sys
from pathlib import Path


def test_import_separator_does_not_import_numpy():
    sys.modules.pop("numpy", None)
    sys.modules.pop("separator", None)
    import separator

    assert "numpy" not in sys.modules
    assert hasattr(separator, "model_path")


def test_model_path_follows_app_paths(monkeypatch, tmp_path):
    import app_paths
    import separator

    monkeypatch.setattr(app_paths, "models_dir", lambda: tmp_path / "models")
    assert separator.model_path() == tmp_path / "models" / "baseline.pth"


def test_inference_dataset_does_not_import_tqdm_at_module_load():
    tree = ast.parse(Path("lib/dataset.py").read_text())
    top_level_imports = [
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    ]
    assert "tqdm" not in top_level_imports
