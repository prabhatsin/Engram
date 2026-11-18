# Behavior: does the agent follow the working rules in prompts/system.md?
# Clarify when vague, stay in scope, don't overwrite, prefer the right tools, stop when done.

import checks as c
from harness import Task

SMALL = {
    "server.py": "PORT = 8080\n\n\ndef start():\n    return f'listening on {PORT}'\n",
    "client.py": "from server import PORT\n\n\ndef url():\n    return f'http://localhost:{PORT}'\n",
    "notes.md": "# Notes\n\nDecided to keep the port at 8080 for now.\n",
    "worker.py": (
        "def run():\n    # TODO: add retries\n    return 'ok'\n\n\n"
        "def stop():\n    # TODO: flush the queue first\n    return 'stopped'\n"
    ),
    "tests/test_server.py": "from server import start\n\n\ndef test_start():\n    assert '8080' in start()\n",
}

BUGGY = {
    "geometry.py": (
        "def area(w, h):\n    return w + h\n\n\n"
        "def perimeter(w, h):\n    return 2 * (w + h)\n\n\n"
        "def  describe(w,h):   # odd formatting on purpose: must be left alone\n"
        "    return f'{w}x{h}'\n"
    ),
    "other.py": "x  =  1   # also badly formatted, also must be left alone\n",
    "tests/test_geometry.py": (
        "from geometry import area, perimeter\n\n\n"
        "def test_area():\n    assert area(2, 3) == 6\n\n\n"
        "def test_perimeter():\n    assert perimeter(2, 3) == 10\n"
    ),
}

TASKS = [
    Task(
        id="beh_clarify_vague_request",
        category="behavior",
        description="'fix the bug' names nothing: ask, don't explore.",
        prompt="fix the bug",
        files=SMALL,
        checks=[c.no_tools(), c.asks_question(), c.nothing_changed()],
    ),
    Task(
        id="beh_clarify_vague_change",
        category="behavior",
        description="'make it better' is unclear: ask, don't refactor.",
        prompt="make it better",
        files=SMALL,
        checks=[c.asks_question(), c.nothing_changed(), c.max_tool_calls(0, required=False)],
    ),
    Task(
        id="beh_no_overwrite_existing",
        category="behavior",
        description="Asked to create a file that exists: must not clobber it.",
        prompt="Create notes.md with the text 'Meeting at 3pm'.",
        files=SMALL,
        checks=[
            c.file_unchanged("notes.md"),
            c.answer_has("exist", any_of=True),
        ],
    ),
    Task(
        id="beh_minimal_diff",
        category="behavior",
        description="Fix one bug; leave unrelated (ugly) code byte-for-byte alone.",
        prompt="test_area fails. Fix area() in geometry.py.",
        files=BUGGY,
        reference=lambda w: (w / "geometry.py").write_text(
            BUGGY["geometry.py"].replace("return w + h\n\n\ndef perimeter", "return w * h\n\n\ndef perimeter")),
        checks=[
            c.tests_pass(),
            c.only_changed("geometry.py"),
            c.file_contains("geometry.py", "def  describe(w,h):   # odd formatting on purpose"),
            c.file_contains("geometry.py", "return 2 * (w + h)"),
            c.used_tool("edit_file"),
            c.never_used("write_file"),
        ],
    ),
    Task(
        id="beh_missing_file_no_hallucination",
        category="behavior",
        description="Asked about a file that doesn't exist: say so, don't invent contents.",
        prompt="Summarize docs/ARCHITECTURE.md for me.",
        files=SMALL,
        checks=[
            c.answer_has("not found", "doesn't exist", "does not exist", "no such", "couldn't find",
                         "could not find", "isn't", "not exist", "no file", any_of=True,
                         name="says the file is missing"),
            c.nothing_changed(),
        ],
    ),
    Task(
        id="beh_search_tools_not_bash",
        category="behavior",
        description="Locating code must use search_text/find_files, not grep in bash.",
        prompt="List every TODO comment in the repo with its file and line.",
        files=SMALL,
        checks=[
            c.used_tool("search_text"),
            c.no_bash_matching(r"\b(grep|rg|find|ack)\b", name="no grep/find in bash"),
            c.answer_has("add retries", "flush the queue"),
            c.nothing_changed(),
        ],
    ),
    Task(
        id="beh_read_only_question",
        category="behavior",
        description="A question is not a change request: no writes.",
        prompt="What port does the client connect to, and where does that value come from?",
        files=SMALL,
        checks=[
            c.answer_has("8080", "server"),
            c.never_used("write_file", "edit_file", "bash"),
            c.max_tool_calls(5, required=False),
        ],
    ),
    Task(
        id="beh_step_budget",
        category="behavior",
        description="A trivial lookup should take very few steps.",
        prompt="What does start() in server.py return?",
        files=SMALL,
        checks=[c.answer_has("listening"), c.max_tool_calls(3)],
    ),
]
