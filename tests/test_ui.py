import pytest
from rich.console import Console
from engram import ui


@pytest.fixture
def out(monkeypatch):
    """Swap ui's consoles for recording ones; returns a function that reads stdout text."""
    con = Console(record=True, width=120)
    err = Console(record=True, width=120)
    monkeypatch.setattr(ui, "console", con)
    monkeypatch.setattr(ui, "err_console", err)
    out = lambda: con.export_text()
    out.err = lambda: err.export_text()
    return out


def test_tool_call_shows_name_and_path(out):
    ui.RichHooks().on_tool_call("read_file", {"path": "notes/x.txt"})
    text = out()
    assert "read_file" in text and "notes/x.txt" in text


def test_tool_call_truncates_long_args(out):
    ui.RichHooks().on_tool_call("bash", {"command": "echo " + "a" * 500})
    assert len(out().strip()) < 130


def test_success_shows_check(out):
    ui.RichHooks().on_tool_result("read_file", {"result": "line one\nline two"})
    text = out()
    assert "✓" in text and "line one" in text and "line two" not in text


def test_error_shows_cross(out):
    ui.RichHooks().on_tool_result("read_file", {"error": "File not found: x"})
    text = out()
    assert "✗" in text and "File not found" in text


def test_empty_answer_is_labelled(out):
    ui.show_answer("")
    assert "(The model returned no text.)" in out()


def test_answer_renders_markdown(out):
    ui.show_answer("**hello**")
    assert "hello" in out() and "**" not in out()


def test_error_goes_to_err_console(out):
    ui.show_error("boom")
    assert "Error: boom" in out.err()
    assert "boom" not in out()


def test_model_end_without_start_is_safe(out):
    hooks = ui.RichHooks()
    hooks.on_model_end()
    hooks.on_model_end()


def test_model_start_then_end_twice_is_safe(out):
    hooks = ui.RichHooks()
    hooks.on_model_start(1)
    hooks.on_model_end()
    hooks.on_model_end()
