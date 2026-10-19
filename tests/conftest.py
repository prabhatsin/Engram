import pytest
from engram import config, session

@pytest.fixture(autouse=True)
def repo_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path.resolve())
    session.reset()
    return tmp_path.resolve()