from types import SimpleNamespace as NS
import pytest
from engram import config
from engram.mcp import github


def result(text="x", err=False):
    return NS(isError=err, content=[NS(type="text", text=text), NS(type="image", text="ignored")])

def test_text_of_joins_text_parts_only():
    assert github._text_of(result("hello")) == "hello"

def test_text_of_error_raises():
    with pytest.raises(github.MCPError, match="bad token"):
        github._text_of(result("bad token", err=True))

def test_text_of_truncates(monkeypatch):
    monkeypatch.setattr(config, "MAX_MCP_OUTPUT_CHARS", 5)
    assert github._text_of(result("123456789")).startswith("12345\n...[output truncated]")

def test_start_without_token_is_clear(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(github.MCPError, match="GITHUB_TOKEN"):
        github.GitHubMCP().start()

def test_call_before_start_is_clear():
    with pytest.raises(github.MCPError, match="not connected"):
        github.GitHubMCP(token="x").call_tool("get_me", {})