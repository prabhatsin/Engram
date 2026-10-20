import pytest
from engram import config
from engram.memory import store


class FakeMemory:
    def __init__(self, results=None, fail=False):
        self.results, self.fail, self.added = results or [], fail, []
    def get_all(self, filters):
        if self.fail:
            raise RuntimeError("db locked")
        self.filters = filters
        return {"results": self.results}
    def add(self, messages, user_id):
        if self.fail:
            raise RuntimeError("db locked")
        self.added.append((messages, user_id))


@pytest.fixture
def fake(monkeypatch):
    def use(**kw):
        f = FakeMemory(**kw)
        monkeypatch.setattr(store, "_memory", f)
        return f
    return use


def test_recall_returns_memory_strings(fake):
    fake(results=[{"memory": "tests run with pytest -q"}, {"memory": "uses black"}])
    assert store.recall() == ["tests run with pytest -q", "uses black"]

def test_recall_is_scoped_to_this_repo(fake, repo_root):
    f = fake()
    store.recall()
    assert f.filters == {"user_id": f"repo:{repo_root}"}

def test_recall_is_capped(fake, monkeypatch):
    monkeypatch.setattr(config, "MAX_RECALL", 2)
    fake(results=[{"memory": str(i)} for i in range(5)])
    assert store.recall() == ["0", "1"]

def test_recall_failure_becomes_store_error(fake):
    fake(fail=True)
    with pytest.raises(store.MemoryStoreError, match="db locked"):
        store.recall()

def test_remember_passes_messages_and_scope(fake, repo_root):
    f = fake()
    msgs = [{"role": "user", "content": "always use pytest -q"}]
    store.remember(msgs)
    assert f.added == [(msgs, f"repo:{repo_root}")]

def test_remember_empty_is_noop(fake):
    f = fake()
    store.remember([])
    assert f.added == []

def test_remember_failure_becomes_store_error(fake):
    fake(fail=True)
    with pytest.raises(store.MemoryStoreError):
        store.remember([{"role": "user", "content": "x"}])

def test_missing_key_is_clear(monkeypatch):
    monkeypatch.setattr(store, "_memory", None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(store.MemoryStoreError, match="GEMINI_API_KEY"):
        store.recall()

from types import SimpleNamespace

def test_close_closes_client_and_resets(monkeypatch):
    closed = []
    fake_mem = SimpleNamespace(vector_store=SimpleNamespace(
        client=SimpleNamespace(close=lambda: closed.append(True))))
    monkeypatch.setattr(store, "_memory", fake_mem)
    store.close()
    assert closed == [True]
    assert store._memory is None

def test_close_without_memory_is_noop(monkeypatch):
    monkeypatch.setattr(store, "_memory", None)
    store.close()

def test_close_swallows_errors(monkeypatch):
    def boom():
        raise RuntimeError("x")
    fake_mem = SimpleNamespace(vector_store=SimpleNamespace(client=SimpleNamespace(close=boom)))
    monkeypatch.setattr(store, "_memory", fake_mem)
    store.close()
    assert store._memory is None

def test_scrub_drops_secret_turn_and_its_reply():
    msgs = [
        {"role": "user", "content": "use black"}, {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "my API key is sk-test-12345"}, {"role": "assistant", "content": "noted"},
        {"role": "user", "content": "run pytest -q"}, {"role": "assistant", "content": "ok"},
    ]
    assert [m["content"] for m in store.scrub(msgs)] == ["use black", "ok", "run pytest -q", "ok"]

def test_remember_never_sends_secrets(fake):
    f = fake()
    store.remember([{"role": "user", "content": "password = hunter2"},
                    {"role": "assistant", "content": "ok"}])
    assert f.added == []

