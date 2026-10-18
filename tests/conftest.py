
import pytest
from engram import config

@pytest.fixture(autouse=True)
def repo_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path.resolve())
    return tmp_path.resolve()