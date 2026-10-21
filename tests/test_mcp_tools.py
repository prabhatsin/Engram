import pytest
from engram import loop
from engram.mcp import tools as mt
from engram.mcp.github import MCPError
from engram.tools import registry
from engram.tools.tool import declaration
from engram import approval

SCHEMA = {"type": "object", "properties": {"owner": {"type": "string"}, "number": {"type": "integer"}},
          "required": ["owner", "number"], "additionalProperties": False, "$schema": "x"}


class FakeClient:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail
    def list_tools(self):
        return [
            {"name": "get_issue", "description": "Get an issue", "input_schema": SCHEMA},
            {"name": "list_issues", "description": "List", "input_schema": SCHEMA},
            {"name": "search_code", "description": "Search", "input_schema": SCHEMA},
            {"name": "create_pull_request", "description": "Writes", "input_schema": SCHEMA},
            {"name": "get_me", "description": "No args", "input_schema": {"type": "object", "properties": {}}},
        ]
    def call_tool(self, name, args):
        if self.fail:
            raise MCPError("rate limited")
        self.calls.append((name, args))
        return "ISSUE TEXT"


@pytest.fixture
def registered(monkeypatch):
    monkeypatch.setattr(registry, "TOOLS", list(registry.TOOLS))     # restore after the test
    c = FakeClient()
    registry.register(mt.build_tools(c))
    return c


def test_only_read_tools_and_the_approved_write_are_built():
    names = [t["name"] for t in mt.build_tools(FakeClient())]
    assert names == ["github_get_issue", "github_list_issues", "github_search_code",
                     "github_create_pull_request"]

def test_declaration_uses_the_cleaned_schema():
    d = declaration(mt.build_tools(FakeClient())[0])
    assert d["name"] == "github_get_issue"
    assert d["parameters"] == {"type": "object", "required": ["owner", "number"],
                               "properties": {"owner": {"type": "string"}, "number": {"type": "integer"}}}

def test_clean_schema_flattens_anyof_and_type_lists():
    s = mt.clean_schema({"type": "object", "properties": {
        "a": {"anyOf": [{"type": "null"}, {"type": "string"}], "description": "d"},
        "b": {"type": ["integer", "null"], "default": 1}}})
    assert s["properties"]["a"] == {"type": "string", "description": "d"}
    assert s["properties"]["b"] == {"type": "integer"}

def test_execute_tool_calls_server_with_real_name(registered):
    out = loop.execute_tool({"name": "github_get_issue", "args": {"owner": "me", "number": 3}})
    assert out == {"result": "ISSUE TEXT"}
    assert registered.calls == [("get_issue", {"owner": "me", "number": 3})]

def test_server_error_becomes_a_normal_tool_error(monkeypatch):
    monkeypatch.setattr(registry, "TOOLS", list(registry.TOOLS))
    registry.register(mt.build_tools(FakeClient(fail=True)))
    out = loop.execute_tool({"name": "github_get_issue", "args": {"owner": "me", "number": 3}})
    assert "error" in out and "rate limited" in out["error"]

def test_register_replaces_same_name(monkeypatch):
    monkeypatch.setattr(registry, "TOOLS", list(registry.TOOLS))
    registry.register(mt.build_tools(FakeClient()))
    n = len(registry.TOOLS)
    registry.register(mt.build_tools(FakeClient()))
    assert len(registry.TOOLS) == n

def test_local_tools_have_no_schema_key():
    assert all("schema" not in t for t in registry.TOOLS if not t["name"].startswith("github_"))

def test_extra_read_tools_are_included_and_writes_are_not():
    class C(FakeClient):
        def list_tools(self):
            return super().list_tools() + [
                {"name": "issue_read", "description": "Read", "input_schema": SCHEMA},
                {"name": "issue_write", "description": "Write", "input_schema": SCHEMA},
                {"name": "merge_pull_request", "description": "Write", "input_schema": SCHEMA},
            ]
    names = [t["name"] for t in mt.build_tools(C())]
    assert "github_issue_read" in names
    assert "github_issue_write" not in names
    assert "github_merge_pull_request" not in names

def _write_call(monkeypatch, answer):
    monkeypatch.setattr(registry, "TOOLS", list(registry.TOOLS))
    c = FakeClient()
    registry.register(mt.build_tools(c))
    monkeypatch.setattr(approval, "ask", lambda s: answer)
    out = loop.execute_tool({"name": "github_create_pull_request",
                             "args": {"owner": "me", "number": 1}})
    return c, out

def test_write_tool_runs_only_after_approval(monkeypatch):
    c, out = _write_call(monkeypatch, True)
    assert out == {"result": "ISSUE TEXT"}
    assert c.calls == [("create_pull_request", {"owner": "me", "number": 1})]

def test_declined_write_never_reaches_github(monkeypatch):
    c, out = _write_call(monkeypatch, False)
    assert "declined" in out["error"]
    assert c.calls == []

def test_dangerous_tools_are_never_exposed():
    class C(FakeClient):
        def list_tools(self):
            extra = ("merge_pull_request", "delete_file", "push_files", "create_branch")
            return super().list_tools() + [
                {"name": n, "description": "w", "input_schema": SCHEMA} for n in extra]
    names = [t["name"] for t in mt.build_tools(C())]
    for n in ("merge_pull_request", "delete_file", "push_files", "create_branch"):
        assert f"github_{n}" not in names