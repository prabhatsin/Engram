import pytest
from engram import loop, main as main_mod, provider, session


def fake_run(monkeypatch, behavior):
    calls = []
    def run(prompt, history=None):          # matches the new signature
        calls.append(prompt)
        if isinstance(behavior, BaseException):
            raise behavior
        return behavior, []                 # same (text, history) shape as the real one
    monkeypatch.setattr(loop, "run_agent", run)
    return calls


def feed(monkeypatch, *lines):
    """Script what the user types. An exception item is raised instead of returned."""
    it = iter(lines)
    def fake_input(prompt=""):
        item = next(it)
        if isinstance(item, BaseException):
            raise item
        return item
    monkeypatch.setattr("builtins.input", fake_input)


# ---------- one-shot mode (prompt on the command line) ----------

def test_prints_the_answer_and_exits_zero(monkeypatch, capsys):
    calls = fake_run(monkeypatch, "all done")
    assert main_mod.main(["fix", "the", "bug"]) == 0
    assert capsys.readouterr().out == "all done\n"
    assert calls == ["fix the bug"]

def test_prompt_is_trimmed(monkeypatch):
    calls = fake_run(monkeypatch, "ok")
    main_mod.main(["  hello  "])
    assert calls == ["hello"]

@pytest.mark.parametrize("argv", [[""], ["   "]])
def test_empty_prompt_shows_usage_and_skips_the_model(monkeypatch, capsys, argv):
    calls = fake_run(monkeypatch, "ok")
    assert main_mod.main(argv) == 2
    assert "Usage" in capsys.readouterr().err
    assert calls == []

def test_agent_error_is_clean(monkeypatch, capsys):
    fake_run(monkeypatch, loop.AgentError("Stopped after 25 steps"))
    assert main_mod.main(["go"]) == 1
    captured = capsys.readouterr()
    assert "Error: Stopped after 25 steps" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""

def test_provider_error_is_clean(monkeypatch, capsys):
    fake_run(monkeypatch, provider.ProviderError("GEMINI_API_KEY is missing"))
    assert main_mod.main(["go"]) == 1
    assert "GEMINI_API_KEY is missing" in capsys.readouterr().err

def test_ctrl_c_exits_130(monkeypatch, capsys):
    fake_run(monkeypatch, KeyboardInterrupt())
    assert main_mod.main(["go"]) == 130
    assert "Interrupted" in capsys.readouterr().err

def test_empty_answer_is_labelled(monkeypatch, capsys):
    fake_run(monkeypatch, None)
    assert main_mod.main(["go"]) == 0
    assert "no text" in capsys.readouterr().out

def test_unexpected_errors_are_not_hidden(monkeypatch):
    fake_run(monkeypatch, ValueError("our bug"))
    with pytest.raises(ValueError):
        main_mod.main(["go"])

def test_defaults_to_command_line_arguments(monkeypatch):
    calls = fake_run(monkeypatch, "ok")
    monkeypatch.setattr(main_mod.sys, "argv", ["engram", "from", "argv"])
    assert main_mod.main() == 0
    assert calls == ["from argv"]


# ---------- chat mode (no arguments) ----------

def test_no_args_starts_chat(monkeypatch):
    monkeypatch.setattr(main_mod.sys, "argv", ["engram"])
    calls = fake_run(monkeypatch, "ok")
    feed(monkeypatch, "hi", "exit")
    assert main_mod.main() == 0
    assert calls == ["hi"]

def test_chat_exit_command(monkeypatch):
    calls = fake_run(monkeypatch, "ok")
    feed(monkeypatch, "exit")
    assert main_mod.main([]) == 0
    assert calls == []

def test_chat_quit_command(monkeypatch):
    fake_run(monkeypatch, "ok")
    feed(monkeypatch, "quit")
    assert main_mod.main([]) == 0

def test_chat_ctrl_d_exits_zero(monkeypatch):
    fake_run(monkeypatch, "ok")
    feed(monkeypatch, EOFError())
    assert main_mod.main([]) == 0

def test_chat_ctrl_c_at_prompt_exits_130(monkeypatch):
    fake_run(monkeypatch, "ok")
    feed(monkeypatch, KeyboardInterrupt())
    assert main_mod.main([]) == 130

def test_chat_skips_empty_lines(monkeypatch):
    calls = fake_run(monkeypatch, "ok")
    feed(monkeypatch, "", "   ", "hi", "exit")
    assert main_mod.main([]) == 0
    assert calls == ["hi"]

def test_chat_prints_each_answer(monkeypatch, capsys):
    fake_run(monkeypatch, "pong")
    feed(monkeypatch, "ping", "exit")
    main_mod.main([])
    assert "pong" in capsys.readouterr().out

def test_chat_empty_answer_is_labelled(monkeypatch, capsys):
    fake_run(monkeypatch, None)
    feed(monkeypatch, "go", "exit")
    assert main_mod.main([]) == 0
    assert "no text" in capsys.readouterr().out

def test_chat_passes_history_between_turns(monkeypatch):
    seen = []
    def run(prompt, history=None):
        seen.append(list(history or []))
        return "ok", (history or []) + [prompt]