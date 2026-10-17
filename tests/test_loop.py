
from types import SimpleNamespace
from engram import loop, provider

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
    sent_back = seen[1][-1].parts[0].function_response.response
    assert sent_back["result"] == "hello"