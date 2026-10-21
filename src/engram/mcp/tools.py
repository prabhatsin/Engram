"""Converts MCP tools into Engram tool dicts. Does not import the MCP SDK."""
from pydantic import BaseModel, ConfigDict
from ..tools.tool import make_tool
from .. import approval

WRITE_TOOLS = ("create_pull_request", "add_issue_comment")   # exposed, but every call asks first

READ_ONLY_PREFIXES = ("get_", "list_", "search_")
EXTRA_READ_TOOLS = ("issue_read", "pull_request_read")   # read-only, but don't match the prefixes
_KEEP = {"type", "description", "properties", "required", "items", "enum"}


class AnyArgs(BaseModel):
    """Accepts any arguments. The MCP server does the real validation."""
    model_config = ConfigDict(extra="allow")


def clean_schema(s):
    """Keep only the JSON-schema keys Gemini accepts; flatten anyOf and type lists."""
    if not isinstance(s, dict):
        return s
    s = dict(s)
    for key in ("anyOf", "oneOf"):
        if key in s:
            options = [o for o in s.pop(key) if o.get("type") != "null"]
            if options:
                s = {**options[0], **s}          # outer keys (like description) win
    if isinstance(s.get("type"), list):
        s["type"] = next((t for t in s["type"] if t != "null"), "string")
    out = {k: v for k, v in s.items() if k in _KEEP}
    if "properties" in out:
        out["properties"] = {k: clean_schema(v) for k, v in out["properties"].items()}
    if "items" in out:
        out["items"] = clean_schema(out["items"])
    return out



def _summary(name, kwargs):
    return f"github {name} " + " ".join(f"{k}={str(v)[:80]!r}" for k, v in kwargs.items())


def _runner(client, mcp_name, confirm=False):
    def run(**kwargs):
        if confirm and not approval.ask(_summary(mcp_name, kwargs)):
            raise PermissionError(
                "The user declined this GitHub action. Do not retry it. Ask the user what to do instead.")
        return client.call_tool(mcp_name, kwargs)
    return run


def build_tools(client, prefixes=READ_ONLY_PREFIXES):
    tools = []
    for t in client.list_tools():
        name = t["name"]
        is_write = name in WRITE_TOOLS
        if not (is_write or name.startswith(prefixes) or name in EXTRA_READ_TOOLS):
            continue
        schema = clean_schema(t["input_schema"] or {})
        if not schema.get("properties"):
            continue                    # no-argument tools (like get_me) are skipped:
                                        # an empty object schema can be rejected by Gemini
        schema["type"] = "object"
        tools.append(make_tool(
            name=f"github_{name}",
            description=f"[GitHub{', asks the user first' if is_write else ''}] {t['description']}".strip(),
            args_model=AnyArgs,
            func=_runner(client, name, confirm=is_write),
            schema=schema,
        ))
    return tools