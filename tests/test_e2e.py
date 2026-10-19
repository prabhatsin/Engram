import shlex
import sys
from types import SimpleNamespace
from engram import approval, loop, provider

PYTEST = f"{shlex.quote(sys.executable)} -m pytest -q -p no:cacheprovider"


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

def result_of(history):
    return history[-1].parts[0].function_response.response

def call(name, **args):
    return {"name": name, "args": args}

def make_buggy_repo(repo_root):
    (repo_root / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (repo_root / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )

def allow_all(monkeypatch):
    asked = []
    monkeypatch.setattr(approval, "ask", lambda command: asked.append(command) or True)
    return asked


def test_fix_a_failing_test_end_to_end(monkeypatch, repo_root):
    make_buggy_repo(repo_root)
    asked = allow_all(monkeypatch)
    seen = script(monkeypatch, [
        reply(calls=[call("bash", command=PYTEST)]),
        reply(calls=[call("read_file", path="calc.py")]),
        reply(calls=[call("edit_file", path="calc.py", old_text="a - b", new_text="a + b")]),
        reply(calls=[call("bash", command=PYTEST)]),
        reply(text="Fixed add(): it subtracted instead of adding. Tests pass."),
    ])

    answer, _ = loop.run_agent("fix the failing test")

    assert answer.startswith("Fixed add()")
    assert (repo_root / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
    first_run = result_of(seen[1])["result"]
    assert first_run.startswith("exit code: 1")
    assert "failed" in first_run.lower()
    assert "Edited calc.py" in result_of(seen[3])["result"]
    assert result_of(seen[4])["result"].startswith("exit code: 0")
    assert len(asked) == 2


def test_edit_before_reading_is_refused_then_recovers(monkeypatch, repo_root):
    make_buggy_repo(repo_root)
    allow_all(monkeypatch)
    seen = script(monkeypatch, [
        reply(calls=[call("edit_file", path="calc.py", old_text="a - b", new_text="a + b")]),
        reply(calls=[call("read_file", path="calc.py")]),
        reply(calls=[call("edit_file", path="calc.py", old_text="a - b", new_text="a + b")]),
        reply(calls=[call("bash", command=PYTEST)]),
        reply(text="done"),
    ])

    assert loop.run_agent("fix add")[0] == "done"

    assert "not read" in result_of(seen[1])["error"]
    assert (repo_root / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
    assert result_of(seen[4])["result"].startswith("exit code: 0")


def test_declined_test_run_does_not_stop_the_task(monkeypatch, repo_root):
    make_buggy_repo(repo_root)
    monkeypatch.setattr(approval, "ask", lambda command: False)
    seen = script(monkeypatch, [
        reply(calls=[call("read_file", path="calc.py")]),
        reply(calls=[call("edit_file", path="calc.py", old_text="a - b", new_text="a + b")]),
        reply(calls=[call("bash", command=PYTEST)]),
        reply(text="Fixed it, but you declined the test run so it is unverified."),
    ])

    answer, _ = loop.run_agent("fix add")

    assert "unverified" in answer
    assert "declined" in result_of(seen[3])["error"]
    assert (repo_root / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"


def test_blocked_step_in_the_middle_does_not_derail_the_run(monkeypatch, repo_root):
    make_buggy_repo(repo_root)
    allow_all(monkeypatch)
    (repo_root.parent / "outside.txt").write_text("secret")
    seen = script(monkeypatch, [
        reply(calls=[call("read_file", path="../outside.txt")]),
        reply(calls=[call("read_file", path="calc.py")]),
        reply(calls=[call("edit_file", path="calc.py", old_text="a - b", new_text="a + b")]),
        reply(text="done"),
    ])

    assert loop.run_agent("fix add")[0] == "done"

    blocked = result_of(seen[1])
    assert "Blocked" in blocked["error"]
    assert "secret" not in str(blocked)
    assert (repo_root / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"


