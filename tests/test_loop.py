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
    assert loop.run_agent("hello")[0] == "hi"
    assert len(seen) == 1

def test_tool_call_then_answer(monkeypatch, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": str(f)}}]),
        reply(text="It says hello"),
    ])
    assert loop.run_agent("what is in a.txt")[0] == "It says hello"
    assert [len(h) for h in seen] == [1, 3]
    assert sent_back_after(seen)["result"] == "hello"

def test_unknown_tool_is_reported_to_model(monkeypatch):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "nope", "args": {}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    sent_back = sent_back_after(seen)
    assert "Unknown tool" in sent_back["error"]
    assert "read_file" in sent_back["error"]
    assert "result" not in sent_back

def test_missing_argument_reported(monkeypatch):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    sent_back = sent_back_after(seen)
    assert "Invalid arguments" in sent_back["error"]
    assert "path" in sent_back["error"]
    assert "result" not in sent_back

def test_wrong_type_argument_reported(monkeypatch):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": 123}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert "path" in sent_back_after(seen)["error"]

def test_extra_argument_is_ignored(monkeypatch, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": str(f), "bogus": 1}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert sent_back_after(seen)["result"] == "hello"

def test_missing_file_error_reported(monkeypatch, tmp_path):
    missing = tmp_path / "nope.txt"
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": str(missing)}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    sent_back = sent_back_after(seen)
    assert "FileNotFoundError" in sent_back["error"]
    assert "result" not in sent_back

def test_directory_instead_of_file_reported(monkeypatch, tmp_path):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": str(tmp_path)}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert "IsADirectoryError" in sent_back_after(seen)["error"]

def test_any_tool_exception_is_reported(monkeypatch):
    def boom(path):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(registry, "TOOLS", [make_tool("bad", "x", ReadArgs, boom)])
    seen = script(monkeypatch, [
        reply(calls=[{"name": "bad", "args": {"path": "a"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
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
    assert loop.run_agent("go")[0] == "ok"
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
    assert loop.run_agent("go")[0] == "ok"
    sent_back = sent_back_after(seen)
    assert "protected" in sent_back["error"]
    assert "abc" not in str(sent_back)

def test_relative_path_resolves_against_repo_root(monkeypatch, tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": "a.txt"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert sent_back_after(seen)["result"] == "hello"


def test_write_file_creates_file(monkeypatch, repo_root):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "write_file", "args": {"path": "new/a.txt", "content": "hi"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert (repo_root / "new" / "a.txt").read_text() == "hi"
    assert "Created" in sent_back_after(seen)["result"]

def test_write_file_does_not_overwrite_by_default(monkeypatch, repo_root):
    (repo_root / "a.txt").write_text("original")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "write_file", "args": {"path": "a.txt", "content": "new"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert "FileExistsError" in sent_back_after(seen)["error"]
    assert (repo_root / "a.txt").read_text() == "original"

def test_write_file_overwrite_flag_works(monkeypatch, repo_root):
    (repo_root / "a.txt").write_text("original")
    script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": "a.txt"}}]),
        reply(calls=[{"name": "write_file", "args": {"path": "a.txt", "content": "new", "overwrite": True}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert (repo_root / "a.txt").read_text() == "new"

def test_write_to_env_is_blocked(monkeypatch, repo_root):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "write_file", "args": {"path": ".env", "content": "KEY=1"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert "protected" in sent_back_after(seen)["error"]
    assert not (repo_root / ".env").exists()

def test_write_outside_repo_is_blocked(monkeypatch, repo_root):
    outside = repo_root.parent / "escaped.txt"
    seen = script(monkeypatch, [
        reply(calls=[{"name": "write_file", "args": {"path": "../escaped.txt", "content": "x"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert "Blocked" in sent_back_after(seen)["error"]
    assert not outside.exists()

def test_write_missing_content_is_reported(monkeypatch, repo_root):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "write_file", "args": {"path": "a.txt"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert "content" in sent_back_after(seen)["error"]
    assert not (repo_root / "a.txt").exists()

def test_edit_without_reading_is_refused(monkeypatch, repo_root):
    (repo_root / "a.txt").write_text("hello")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "edit_file", "args": {"path": "a.txt", "old_text": "hello", "new_text": "bye"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert "not read" in sent_back_after(seen)["error"]
    assert (repo_root / "a.txt").read_text() == "hello"

def test_read_then_edit_in_the_same_run(monkeypatch, repo_root):
    (repo_root / "a.txt").write_text("hello world")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": "a.txt"}}]),
        reply(calls=[{"name": "edit_file", "args": {"path": "a.txt", "old_text": "world", "new_text": "there"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert (repo_root / "a.txt").read_text() == "hello there"
    assert "Edited" in seen[2][-1].parts[0].function_response.response["result"]

def test_reads_carry_over_between_turns(monkeypatch, repo_root):
    (repo_root / "a.txt").write_text("hello")
    script(monkeypatch, [
        reply(calls=[{"name": "read_file", "args": {"path": "a.txt"}}]),
        reply(text="ok"),
    ])
    _, history = loop.run_agent("first")
    script(monkeypatch, [
        reply(calls=[{"name": "edit_file", "args": {"path": "a.txt", "old_text": "hello", "new_text": "bye"}}]),
        reply(text="ok"),
    ])
    loop.run_agent("second", history)
    assert (repo_root / "a.txt").read_text() == "bye"

def test_file_created_by_write_can_be_edited(monkeypatch, repo_root):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "write_file", "args": {"path": "n.txt", "content": "one"}}]),
        reply(calls=[{"name": "edit_file", "args": {"path": "n.txt", "old_text": "one", "new_text": "two"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert (repo_root / "n.txt").read_text() == "two"

def test_edit_env_file_is_blocked(monkeypatch, repo_root):
    (repo_root / ".env").write_text("KEY=1")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "edit_file", "args": {"path": ".env", "old_text": "1", "new_text": "2"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert "protected" in sent_back_after(seen)["error"]
    assert (repo_root / ".env").read_text() == "KEY=1"

from engram import approval

def test_bash_safe_command_through_the_loop(monkeypatch):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "bash", "args": {"command": "pwd"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert sent_back_after(seen)["result"].startswith("exit code: 0")

def test_bash_dangerous_command_is_reported(monkeypatch):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "bash", "args": {"command": "sudo rm -rf /"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert "refused" in sent_back_after(seen)["error"]

def test_bash_declined_command_is_reported_and_not_run(monkeypatch, repo_root):
    monkeypatch.setattr(approval, "ask", lambda c: False)
    seen = script(monkeypatch, [
        reply(calls=[{"name": "bash", "args": {"command": "touch marker.txt"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert "declined" in sent_back_after(seen)["error"]
    assert not (repo_root / "marker.txt").exists()

def test_bash_cannot_read_env_file(monkeypatch, repo_root):
    (repo_root / ".env").write_text("SECRET=abc")
    seen = script(monkeypatch, [
        reply(calls=[{"name": "bash", "args": {"command": "cat .env"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    sent_back = sent_back_after(seen)
    assert "refused" in sent_back["error"]
    assert "abc" not in str(sent_back)

def test_bash_missing_command_argument(monkeypatch):
    seen = script(monkeypatch, [
        reply(calls=[{"name": "bash", "args": {}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    assert "command" in sent_back_after(seen)["error"]

def test_failing_command_is_a_result_not_an_error(monkeypatch):
    monkeypatch.setattr(approval, "ask", lambda c: True)
    seen = script(monkeypatch, [
        reply(calls=[{"name": "bash", "args": {"command": "exit 2"}}]),
        reply(text="ok"),
    ])
    assert loop.run_agent("go")[0] == "ok"
    sent_back = sent_back_after(seen)
    assert sent_back["result"].startswith("exit code: 2")
    assert "error" not in sent_back

# ---- step limit ----

def test_stops_at_max_steps(monkeypatch, repo_root):
    (repo_root / "a.txt").write_text("x")
    call = {"name": "read_file", "args": {"path": "a.txt"}}
    seen = script(monkeypatch, [reply(calls=[call]) for _ in range(10)])
    monkeypatch.setattr(loop.config, "MAX_STEPS", 3)
    with pytest.raises(loop.AgentError, match="3 steps"):
        loop.run_agent("go")
    assert len(seen) == 3

def test_final_answer_on_the_last_allowed_step_is_returned(monkeypatch, repo_root):
    (repo_root / "a.txt").write_text("x")
    call = {"name": "read_file", "args": {"path": "a.txt"}}
    script(monkeypatch, [reply(calls=[call]), reply(calls=[call]), reply(text="done")])
    monkeypatch.setattr(loop.config, "MAX_STEPS", 3)
    assert loop.run_agent("go")[0] == "done"


# ---- repeated failures ----

def test_same_failing_call_stops_the_loop(monkeypatch):
    monkeypatch.setattr(loop.config, "MAX_REPEATS", 3)
    call = {"name": "read_file", "args": {}}
    seen = script(monkeypatch, [reply(calls=[call]) for _ in range(10)])
    with pytest.raises(loop.AgentError, match="read_file"):
        loop.run_agent("go")
    assert len(seen) == 3

def test_error_message_includes_the_last_error(monkeypatch):
    monkeypatch.setattr(loop.config, "MAX_REPEATS", 2)
    call = {"name": "nope", "args": {}}
    script(monkeypatch, [reply(calls=[call]) for _ in range(5)])
    with pytest.raises(loop.AgentError, match="Unknown tool"):
        loop.run_agent("go")

def test_different_failing_calls_do_not_trigger(monkeypatch, repo_root):
    monkeypatch.setattr(loop.config, "MAX_REPEATS", 2)
    calls = [
        reply(calls=[{"name": "read_file", "args": {"path": name}}])
        for name in ("a", "b", "c")
    ]
    script(monkeypatch, calls + [reply(text="done")])
    assert loop.run_agent("go")[0] == "done"

def test_argument_order_does_not_hide_a_repeat(monkeypatch):
    monkeypatch.setattr(loop.config, "MAX_REPEATS", 2)
    script(monkeypatch, [
        reply(calls=[{"name": "nope", "args": {"a": 1, "b": 2}}]),
        reply(calls=[{"name": "nope", "args": {"b": 2, "a": 1}}]),
        reply(text="done"),
    ])
    with pytest.raises(loop.AgentError):
        loop.run_agent("go")

def test_success_resets_the_failure_count(monkeypatch):
    monkeypatch.setattr(loop.config, "MAX_REPEATS", 2)
    state = {"n": 0}
    def flaky(path):
        state["n"] += 1
        if state["n"] != 2:
            raise RuntimeError("fail")
        return "ok"
    monkeypatch.setattr(registry, "TOOLS", [make_tool("flaky", "x", ReadArgs, flaky)])
    call = {"name": "flaky", "args": {"path": "a"}}
    script(monkeypatch, [reply(calls=[call]) for _ in range(3)] + [reply(text="done")])
    assert loop.run_agent("go")[0] == "done"

def test_counts_do_not_carry_over_between_runs(monkeypatch):
    monkeypatch.setattr(loop.config, "MAX_REPEATS", 3)
    call = {"name": "nope", "args": {}}
    script(monkeypatch, [reply(calls=[call]), reply(calls=[call]), reply(text="done")])
    assert loop.run_agent("first")[0] == "done"
    script(monkeypatch, [reply(calls=[call]), reply(calls=[call]), reply(text="done")])
    assert loop.run_agent("second")[0] == "done"

def test_history_carries_over(monkeypatch):
    seen = []
    def fake_chat(history, tools=None):
        seen.append(len(history))
        return {"text": "ok", "tool_calls": [], "content": "model-turn"}
    monkeypatch.setattr(loop.provider, "chat", fake_chat)

    _, h1 = loop.run_agent("first")
    _, h2 = loop.run_agent("second", h1)

    assert seen == [1, 3]      # [user] then [user, model, user]
    assert len(h2) == 4


def test_failed_turn_leaves_history_untouched(monkeypatch):
    def boom(history, tools=None):
        raise loop.provider.ProviderError("down")
    monkeypatch.setattr(loop.provider, "chat", boom)

    old = ["u1", "m1"]
    with pytest.raises(loop.AgentError):
        loop.run_agent("again", old)
    assert old == ["u1", "m1"]


def test_failure_after_tool_call_rolls_back(monkeypatch):
    # the real danger: model asked for a tool, then the next call fails
    replies = iter([{"text": "", "tool_calls": [{"name": "nope", "args": {}}],
                     "content": "m-call"}])
    def fake_chat(history, tools=None):
        try:
            return next(replies)
        except StopIteration:
            raise loop.provider.ProviderError("down")
    monkeypatch.setattr(loop.provider, "chat", fake_chat)

    old = ["u1", "m1"]
    with pytest.raises(loop.AgentError):
        loop.run_agent("again", old)
    assert old == ["u1", "m1"]