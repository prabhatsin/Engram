import pytest
from pydantic import ValidationError
from engram import config
from engram.tools import registry
from engram.tools.tool import make_tool
from engram.tools.read import READ_FILE, ReadArgs, read_file


# ---- registry and declarations ----

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

def test_optional_args_are_not_required():
    decls = {d["name"]: d for d in registry.all_declarations()}
    assert decls["find_files"]["parameters"]["required"] == ["pattern"]
    assert decls["search_text"]["parameters"]["required"] == ["query"]
    assert decls["write_file"]["parameters"]["required"] == ["path", "content"]
    assert "default" not in decls["find_files"]["parameters"]["properties"]["path"]
    assert decls["edit_file"]["parameters"]["required"] == ["path", "old_text", "new_text"]

def test_unknown_tool_returns_none():
    assert registry.get_tool("nope") is None

def test_get_tool_finds_tool_that_is_not_first(monkeypatch):
    other = make_tool("other", "x", ReadArgs, lambda path: "")
    monkeypatch.setattr(registry, "TOOLS", [other, READ_FILE])
    assert registry.get_tool("read_file") is READ_FILE

def test_args_model_rejects_missing_path():
    with pytest.raises(ValidationError):
        ReadArgs()

def test_tool_names():
    assert registry.available_tool_names() == [
        "read_file", "find_files", "search_text", "write_file", "edit_file"
    ]


# ---- read_file ----

def test_read_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="nope.txt"):
        read_file(str(tmp_path / "nope.txt"))

def test_read_directory(tmp_path):
    with pytest.raises(IsADirectoryError):
        read_file(str(tmp_path))

def test_read_binary_file(tmp_path):
    f = tmp_path / "img.bin"
    f.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(ValueError, match="binary|null"):
        read_file(str(f))

def test_read_file_with_null_bytes(tmp_path):
    f = tmp_path / "a.dat"
    f.write_bytes(b"abc\x00def")
    with pytest.raises(ValueError, match="null bytes"):
        read_file(str(f))

def test_read_empty_file(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("")
    assert read_file(str(f)) == ""

def test_read_unicode_file(tmp_path):
    f = tmp_path / "u.txt"
    f.write_text("नमस्ते", encoding="utf-8")
    assert read_file(str(f)) == "नमस्ते"

# def test_large_file_is_truncated(monkeypatch, tmp_path):
#     monkeypatch.setattr(config, "MAX_READ_CHARS", 10)
#     f = tmp_path / "big.txt"
#     f.write_text("a" * 50)
#     out = read_file(str(f))
#     assert out.startswith("a" * 10)
#     assert "a" * 11 not in out
#     assert "Truncated" in out
#     assert "50-byte" in out

# def test_file_exactly_at_limit_is_not_truncated(monkeypatch, tmp_path):
#     monkeypatch.setattr(config, "MAX_READ_CHARS", 10)
#     f = tmp_path / "exact.txt"
#     f.write_text("a" * 10)
#     assert read_file(str(f)) == "a" * 10

# def test_file_one_over_limit_is_truncated(monkeypatch, tmp_path):
#     monkeypatch.setattr(config, "MAX_READ_CHARS", 10)
#     f = tmp_path / "over.txt"
#     f.write_text("a" * 11)
#     assert "Truncated" in read_file(str(f))

# def test_large_binary_file_still_rejected(monkeypatch, tmp_path):
#     monkeypatch.setattr(config, "MAX_READ_CHARS", 10)
#     f = tmp_path / "big.bin"
#     f.write_bytes(b"abc\x00" * 100)
#     with pytest.raises(ValueError, match="null bytes"):
#         read_file(str(f))