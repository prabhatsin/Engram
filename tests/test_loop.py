from types import SimpleNamespace
from engram import loop, provider
import pytest
from types import SimpleNamespace
from engram import loop, provider
from engram.tools import registry
from engram.tools.tool import make_tool
from engram.tools.read import ReadArgs
def reply(text=None, calls=None):
    return {"text": text, "tool_calls": calls or [], "content": SimpleNamespace(role="model")}

def script(monkeypatch, replies):
    it = iter(replies)
    seen = []
    def fake_chat(history, tools=None):
        seen.append(list(history))
        return next(it)
    monkeypatch.setattr(provider, "chat", fake_chat)
    return seen

def sent_back_after(seen):
    return seen[1][-1].parts[0].function_response.response

def test_plain_answer_no_tools(monkeypatch):
    seen = script(monkeypatch, [reply(text="hi")])
    assert loop.run_agent("hello") == "hi"
    assert len(seen) == 1

def test_tool_call_then_answer(monkeypatch, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": str(f)}}]),
        reply(text="It says hello"),
    ])
    assert loop.run_agent("what is in a.txt") == "It says hello"
    assert [len(h) for h in seen] == [1, 3]
    assert sent_back_after(seen)["result"] == "hello"

def test_unknown_tool_is_reported_to_model(monkeypatch):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "nope", "args": {}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go") == "ok"
    sent_back = sent_back_after(seen)
    assert "Unknown tool" in sent_back["error"]
    assert "read_file" in sent_back["error"]
    assert "result" not in sent_back

def test_missing_argument_reported(monkeypatch):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go") == "ok"
    sent_back = sent_back_after(seen)
    assert "Invalid arguments" in sent_back["error"]
    assert "path" in sent_back["error"]
    assert "result" not in sent_back

def test_wrong_type_argument_reported(monkeypatch):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": 123}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go") == "ok"
    assert "path" in sent_back_after(seen)["error"]

def test_extra_argument_is_ignored(monkeypatch, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": str(f), "bogus": 1}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go") == "ok"
    assert sent_back_after(seen)["result"] == "hello"

def test_missing_file_error_reported(monkeypatch, tmp_path):
    missing = tmp_path / "nope.txt"
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": str(missing)}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go") == "ok"
    sent_back = sent_back_after(seen)
    assert "FileNotFoundError" in sent_back["error"]
    assert "result" not in sent_back

def test_directory_instead_of_file_reported(monkeypatch, tmp_path):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": str(tmp_path)}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go") == "ok"
    assert "IsADirectoryError" in sent_back_after(seen)["error"]

def test_any_tool_exception_is_reported(monkeypatch):
    def boom(path):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(registry, "TOOLS", [make_tool("bad", "x", ReadArgs, boom)])
    seen = script(monkeypatch, [
        reply(calls=[{"name": "bad", "args": {"path": "a"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go") == "ok"
    err = sent_back_after(seen)["error"]
    assert "RuntimeError" in err
    assert "kaboom" in err

def test_ctrl_c_is_not_swallowed(monkeypatch):
    def interrupt(path):
        raise KeyboardInterrupt
    monkeypatch.setattr(registry, "TOOLS", [make_tool("bad", "x", ReadArgs, interrupt)])
    script(monkeypatch, [reply(calls=[{"name": "bad", "args": {"path": "a"}}])])
    with pytest.raises(KeyboardInterrupt):
        loop.run_agent("go")

def failing_after(monkeypatch, replies):
    it = iter(replies)
    def fake_chat(history, tools=None):
        item = next(it)
        if isinstance(item, Exception):
            raise item
        return item
    monkeypatch.setattr(provider, "chat", fake_chat)

def test_provider_error_on_first_call(monkeypatch):
    failing_after(monkeypatch, [provider.ProviderError("down")])
    with pytest.raises(loop.AgentError, match="step 1") as info:
        loop.run_agent("go")
    assert isinstance(info.value.__cause__, provider.ProviderError)

def test_provider_error_mid_loop(monkeypatch, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    failing_after(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": str(f)}}]),
        provider.ProviderError("rate limited"),
    ])
    with pytest.raises(loop.AgentError, match="step 2") as info:
        loop.run_agent("go")
    assert "1 completed" in str(info.value)
    assert "rate limited" in str(info.value)

def test_non_provider_errors_are_not_disguised(monkeypatch):
    failing_after(monkeypatch, [ValueError("our bug")])
    with pytest.raises(ValueError):
        loop.run_agent("go")


def test_path_outside_repo_blocked_and_tool_not_run(monkeypatch):
    called = {"n": 0}
    def spy(path):
        called["n"] += 1
        return "secret"
    monkeypatch.setattr(registry, "TOOLS", [make_tool("peek", "x", ReadArgs, spy, path_fields=("path",))])
    seen = script(monkeypatch, [
        reply(calls=[{"name": "peek", "args": {"path": "/etc/passwd"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go") == "ok"
    sent_back = sent_back_after(seen)
    assert "Blocked" in sent_back["error"]
    assert "result" not in sent_back
    assert called["n"] == 0

def test_env_file_blocked_in_loop(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("GEMINI_API_KEY=abc")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": ".env"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go") == "ok"
    sent_back = sent_back_after(seen)
    assert "protected" in sent_back["error"]
    assert "abc" not in str(sent_back)

def test_relative_path_resolves_against_repo_root(monkeypatch, tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": "a.txt"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go") == "ok"
    assert sent_back_after(seen)["result"] == "hello"