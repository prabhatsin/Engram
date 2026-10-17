import pytest
from pydantic import ValidationError
from engram.tools import registry
from engram.tools.tool import make_tool
from engram.tools.read import READ_FILE, ReadArgs

def test_read_file_returns_contents(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    tool = registry.get_tool("read_file")
    assert tool["func"](path=str(f)) == "hello"

def test_declaration_has_only_model_facing_fields():
    decl = registry.all_declarations()[0]
    assert set(decl.keys()) == {"name", "description", "parameters"}

def test_declaration_schema_is_clean():
    params = registry.all_declarations()[0]["parameters"]
    assert params["type"] == "object"
    assert params["required"] == ["path"]
    assert params["properties"]["path"]["description"] == "File path"
    assert "title" not in params
    assert "title" not in params["properties"]["path"]

def test_unknown_tool_returns_none():
    assert registry.get_tool("nope") is None

def test_get_tool_finds_tool_that_is_not_first(monkeypatch):
    other = make_tool("other", "x", ReadArgs, lambda path: "")
    monkeypatch.setattr(registry, "TOOLS", [other, READ_FILE])
    assert registry.get_tool("read_file") is READ_FILE

def test_args_model_rejects_missing_path():
    with pytest.raises(ValidationError):
        ReadArgs()