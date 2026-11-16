# Engram: script-by-script reading path

Follow the code the way Python runs it: start at the command, go down into the loop,
then out to each tool and integration. Paths are relative to `src/engram/`.

```
pyproject.toml
   └─► main.py  main()
         ├─► config.py ─► prompts/system.md          (runs on import)
         ├─ one-shot ─► loop.run_agent()
         └─ chat()
              ├─► mcp/github.py ─► mcp/tools.py ─► tools/registry.register()
              ├─► memory/store.recall()
              ├─► loop.run_agent()  ◄── ui.RichHooks
              │     ├─► provider.chat() ─► Gemini
              │     └─► execute_tool()
              │           ├─► tools/registry.get_tool()
              │           ├─► guard.check_args()
              │           └─► tools/read|search|write|edit|bash  (session.py, approval.py)
              └─► memory/store.remember()   (at exit)
```

---

## Step 0: `pyproject.toml` (how the command exists)

- `[project.scripts] engram = "engram.main:main"`: typing `engram` calls `main()` in `main.py`.
- `pythonpath = ["src"]` for tests, so `engram` is importable as a package.

## Step 1: `config.py` (runs first, on import)

`main.py` imports `config`, which runs immediately:
- `load_dotenv()` reads `.env` (`GEMINI_API_KEY`, `ENGRAM_MODEL`, `ENGRAM_REPO`, `GITHUB_TOKEN`).
- Sets `REPO_ROOT` (the folder the agent may touch), every limit (`MAX_STEPS=25`, timeouts, output caps), and the memory and MCP settings.
- Loads `SYSTEM_PROMPT` from `prompts/system.md`.

Read `prompts/system.md` alongside it: these are the rules the model works under.

## Step 2: `main.py` (the entry point)

Read in this order:
1. `main(argv)` (line 112): with arguments it runs **one-shot** (`loop.run_agent(prompt)`); without arguments it runs **chat** (`chat()`).
2. `chat()` (line 92): `connect_github()` → `run_chat()` → in `finally`, `save_memory()` and `github.close()`.
3. `run_chat()` (line 28): `session.reset()`, `store.recall()`, `build_system()`, then the `input("> ")` REPL. Each task goes to `loop.run_agent(...)`.
4. `build_system()` (line 13): appends remembered facts to the system prompt.
5. `connect_github()` and `save_memory()`: covered in Steps 9 and 10.

## Step 3: `loop.py` (the heart of the agent)

1. `run_agent()` (line 65): copies the history (so a failed turn rolls back for free), appends the prompt, then loops:
   call `provider.chat` → if no tool calls, return the text → else run each tool, append the results, repeat.
   It stops at `MAX_STEPS` or after the same call fails `MAX_REPEATS` times.
2. `execute_tool()` (line 28): registry lookup → Pydantic validation → `guard.check_args` → call the function. It always returns `{"result"}` or `{"error"}` and never raises.
3. `Hooks` class (line 55): empty callbacks for the UI (see Step 8).

## Step 4: `provider.py` (talking to Gemini)

- `chat(history, tools, system)` (line 111): builds `GenerateContentConfig`, calls the model, and turns `function_calls` into plain `{name, args}` dicts. It returns `{text, tool_calls, content}`. `content` is the raw message, stored in history so it can be sent back unchanged.
- `call_with_retry()` (line 38): retries 429 and 5xx errors and network errors with exponential backoff; it raises `ProviderError` otherwise.
- `get_client()`: fails fast if the API key is missing.

This is the only file that knows about the Gemini SDK, apart from the `types` used in `loop.py`.

## Step 5: `tools/tool.py` → `tools/registry.py` (what a tool is)

- `tool.py`: `make_tool()` packs a tool into a dict, and `declaration()` turns the Pydantic model into the JSON schema the model sees.
- `registry.py`: the `TOOLS` list, `get_tool(name)`, `all_declarations()`, and `register()` (used by MCP to add GitHub tools at runtime).

## Step 6: `guard.py` + `session.py` (safety rails used by the loop and tools)

- `guard.py`: `check_args()` resolves every field listed in a tool's `path_fields`, and `resolve_in_repo()` blocks paths outside `REPO_ROOT` and protected names (`.env*`, `.git`).
- `session.py`: remembers each file's mtime at the time it was read. Write and edit refuse to run if the file changed since the last read or was never read.

## Step 7: the local tools (`tools/`), easiest first

1. `read.py`: `read_file` rejects directories and binary files, then calls `session.mark_read`.
2. `search.py`: `find_files` and `search_text` wrap ripgrep (`rg`) and skip junk directories and secrets; output is capped.
3. `write.py`: `write_file` and `atomic_write` (temp file + rename); overwriting needs `overwrite=True` and a fresh read.
4. `edit.py`: `edit_file` does an exact-match replace, fails on ambiguous matches and handles CRLF; it reuses `atomic_write`.
5. `bash.py`: `run_bash`: length cap → `denied_reason` (denylist regex) → `is_auto_approved` (plain `ls`, `pwd`, `pytest`, `git status|diff|log` with no shell syntax) or `approval.ask` → subprocess in its own process group with a stripped env (`BASH_ENV_KEYS`), a timeout and capped output.
6. `../approval.py`: `ask()` prints the command and asks y/N. With no TTY, it always declines.

## Step 8: `ui.py` (display only)

`RichHooks(loop.Hooks)` shows the "Thinking…" spinner, the `▸ tool` lines and the ✓/✗ results; `show_answer()` renders Markdown.
The loop calls hooks and never imports Rich, so one-shot mode and tests run without the UI.

## Step 9: `mcp/github.py` → `mcp/tools.py` (GitHub, chat mode only)

- `github.py`: `GitHubMCP` runs an asyncio MCP session on a background thread (`start`, `_main`, `_run`, `list_tools`, `call_tool`, `close`), so the synchronous loop can call it with timeouts.
- `tools.py`: `build_tools()` keeps read-only tools (`get_`, `list_`, `search_`, `issue_read`, `pull_request_read`) plus two write tools (`create_pull_request`, `add_issue_comment`), which go through `approval.ask` first. It renames them to `github_*`, cleans their schemas, and `main.connect_github()` registers them.

## Step 10: `memory/store.py` (per-repo memory, chat mode only)

- `_get()`: lazily builds a Mem0 `Memory` (Gemini LLM + embedder, Qdrant on disk at `~/.engram/memory`).
- `scope()`: one memory space per repo (`repo:<REPO_ROOT>`).
- `recall()` runs at chat start; `remember()` runs at chat exit, after `scrub()` drops turns that look like they contain secrets; `close()` shuts Qdrant down cleanly.

## Step 11: tests (to watch it all work)

Start with `tests/conftest.py` (the fakes for the model, Mem0 and MCP), then `test_loop.py`,
`test_main.py` and `test_e2e.py`. After that, read the per-tool tests (`test_read`, `test_edit`, `test_bash`, `test_guard`, …).
Run them with `pytest -q`. They need no network.

---

### Not wired in yet

- `context.py`: placeholder for history trimming and summarization.
- `provider_open_router.py`: placeholder for an OpenRouter provider.
- `diagrams/`: earlier notes and images (`ARCHITECTURE.md`, PNGs), kept for reference.
