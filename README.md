# Engram

A lightweight terminal coding agent built from scratch in plain Python, with no agent framework. Point it at a git repository, give it a task in plain English, and it reads, searches, edits and tests code through a small set of guarded tools.

Engram is built layer by layer. Each layer is finished, hardened and tested before the next one starts. This README covers what exists today and what is planned.

## Status

| Layer | What it is | Status |
|---|---|---|
| 1. Provider | Gemini client with retries, timeouts, clear errors | Done |
| 2. Agent loop + tools | The think, act, observe cycle and the local tools | In progress |
| 3. MCP / GitHub | Browse repos, issues and pull requests through MCP | Planned |
| 4. Memory (Mem0) | Persistent project context and preferences across sessions | Planned |
| 5. Production hardening | Context management, logging, evals, CLI polish | Planned |

Layer 2 detail:

| Item | Status |
|---|---|
| Loop: unknown tool, bad arguments, tool exceptions returned to the model | Done |
| Loop: provider errors stop the run with a clean message | Done |
| Loop: step limit | Planned |
| Loop: stop on repeated identical failing calls | Planned |
| Path guard (repo-only access, protected files) | Done |
| Tools: `read_file`, `find_files`, `search_text`, `write_file`, `edit_file` | Done |
| `read_file` truncation for huge files and line ranges | Planned |
| Tool: `bash` (timeout, output cap, denylist, confirmation) | Planned |
| CLI: clean error handling and Ctrl+C | Planned |
| System prompt tuning | In progress |
| Scripted end-to-end test (read, edit, run tests, answer) | Planned |

## How it works

```
User prompt
   |
   v
[CLI] --> [Agent loop] <-----------------------+
              |                                |
     builds context (system prompt             |
     + memory + history)                       |
              |                                |
              v                                |
        [Provider] --> LLM                     |
              |                                |
     text reply or tool call?                  |
       |                  |                    |
     done        [Guard: allowed?]             |
                          |                    |
                   [Tool executor] ------------+
              (local tools / MCP tools)   result goes back
                          |
                     [Logger] records everything
```

The loop is small on purpose. It calls the model, checks the request, runs the tool and feeds the result back, until the model replies in plain text. All the reliability comes from the pieces around it.

## Components

| Component | Responsibility |
|---|---|
| `provider` | Talks to the LLM. Retries, timeouts, one error type (`ProviderError`). Hides the vendor behind two functions: `generate_text` and `chat`. |
| `loop` | The cycle, plus limits and stop conditions. Tool failures go back to the model as text. |
| `tools` | Each tool is a name, a description, a Pydantic argument model and a Python function. |
| `registry` | The list of tools, looked up by name. Builds the declarations sent to the model. |
| `guard` | Resolves every path argument and blocks anything outside the repo or in a protected location. |
| `session` | Remembers which files were read this run, so edits can require a prior, fresh read. |
| `context` | Builds the prompt, trims long tool output, summarizes old history (planned). |
| `memory` | Mem0 recall at start, save lessons at end (planned). |
| `mcp` | Starts the GitHub MCP server and converts its tools into Engram's tool format (planned). |
| `config` | Model name, limits, protected names, all in one place. |

## Directory structure

```
engram/
├── src/engram/
│   ├── main.py          # CLI entry point
│   ├── loop.py          # agent loop
│   ├── provider.py      # LLM client
│   ├── config.py        # settings and limits
│   ├── context.py       # prompt building, trimming (planned)
│   ├── guard.py         # path rules
│   ├── session.py       # read tracking
│   ├── tools/
│   │   ├── tool.py      # tool format and declaration builder
│   │   ├── registry.py  # tool lookup
│   │   ├── read.py
│   │   ├── write.py
│   │   ├── edit.py
│   │   ├── search.py    # find_files, search_text (ripgrep)
│   │   └── bash.py      # planned
│   ├── mcp/
│   │   └── github.py    # planned
│   ├── memory/
│   │   └── store.py     # planned
│   └── prompts/
│       └── system.md    # system prompt
├── tests/               # unit tests for tools, guard, loop, provider
├── evals/               # sample repos with seeded bugs (planned)
├── logs/                # run traces (gitignored)
├── .env                 # keys (gitignored)
├── pyproject.toml
└── README.md
```

## Tools

| Tool | What it does | Key safeguards |
|---|---|---|
| `read_file` | Returns a text file's contents | Rejects directories and binary files. Records the read for later edits. |
| `find_files` | Finds files by glob | Skips junk folders, secrets and symlinks. Capped, sorted output. |
| `search_text` | Searches inside files, returns `file:line: text` | Plain text by default, regex opt-in. Skips big and binary files. Capped output. |
| `write_file` | Creates a new file | Refuses to overwrite unless asked. Overwriting needs a prior fresh read. Atomic write. |
| `edit_file` | Replaces exact text in an existing file | Needs a prior fresh read. Fails if the text is missing or matches more than once. Preserves line endings and permissions. |
| `bash` (planned) | Runs a shell command | Timeout, output cap, stripped environment, denylist, confirmation. |

## Reliability and guardrails

Engram is designed to fail safely, visibly and recoverably.

- **Verify before done:** after edits, the agent runs tests or a build and reads the failures (planned with `bash`).
- **Errors go back to the model:** unknown tools, bad arguments, blocked paths and tool exceptions come back as text so the model can adapt. The loop never crashes on them.
- **Validated arguments:** every call is checked against the tool's Pydantic model before it runs. Unknown extra arguments are dropped.
- **One door for paths:** every path argument passes through the guard. Paths resolve before the check, so `..` tricks, symlinks and `./.env` retries are all caught.
- **Protected files:** `.env`, `.env.*` and `.git` are never readable or writable.
- **Edits need fresh reads:** a file must be read this run, and unchanged since, before it can be edited or overwritten.
- **Exact-match edits:** no whole-file rewrites for small changes, and ambiguous matches fail loudly.
- **Atomic writes:** a crash mid-write cannot leave a half-written file.
- **Bounded everything:** retries with backoff, request timeouts, capped search output, a step limit and repeat detection (planned).
- **Work on a branch:** never touch main. Every change is a git diff you can revert (planned).
- **Human approval:** confirmation before bash commands and before push or opening a PR (planned).
- **Untrusted text:** issue and file contents are treated as data, not instructions, to resist prompt injection (planned).

## Planned: MCP and GitHub (Layer 3)

Connect to the GitHub MCP server so the agent can work on existing codebases beyond the local clone: browse repos, read and edit files, and handle issues and pull requests.

- Engram runs inside a local clone of the repo. Local tools do the editing, and MCP handles the GitHub side.
- The pull request flow: create a branch and commit through git, then open the PR through the MCP tool.
- MCP tools are converted into Engram's tool format and pass through the same guard and error handling.

## Planned: memory (Layer 4)

Mem0 stores lessons, not raw chat.

- Repo facts: the test command, code style, folder layout.
- Mistakes and their fixes.
- User preferences.

Recall happens at session start and is injected into the system prompt. An optional reflection step at the end of a task writes two or three lessons, and only lessons from tasks that passed verification are saved, so the agent does not learn from its own failures.

## Planned: production hardening (Layer 5)

- **Context management:** truncate big tool outputs, summarize old turns when history gets long.
- **Logging:** a full trace of every step saved to `logs/`, replacing the temporary `[tool]` print.
- **Evals:** 5 to 10 small tasks (a seeded bug in a sample repo) run after every change to catch regressions.
- **Plan first for big tasks:** the agent writes a short plan, then executes step by step.
- **Fallback model** and optional streaming.
- **Large files:** `read_file` line ranges so the agent can page through big files.

## Setup

Requirements: Python 3.10 or newer, [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) on your PATH, and a Gemini API key.

```bash
python -m venv myenv
source myenv/bin/activate
pip install -e .
pip install pytest
```

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
# optional
ENGRAM_MODEL=your-model-name
ENGRAM_REPO=/path/to/the/repo/you/want/the/agent/to/work/on
```

`ENGRAM_REPO` defaults to the folder you run Engram from.

## Usage

```bash
PYTHONPATH=src python -m engram.main "What does src/engram/config.py do?"
PYTHONPATH=src python -m engram.main "In demo.py change the greeting from hello to hi"
```

## Configuration

All settings live in `src/engram/config.py`:

| Setting | Meaning |
|---|---|
| `MODEL` | Model name, from `ENGRAM_MODEL` |
| `MAX_RETRIES`, `BASE_DELAY` | Retry count and backoff base for temporary API failures |
| `TIMEOUT_SECONDS` | Timeout on every model call |
| `REPO_ROOT` | The folder the agent may touch, from `ENGRAM_REPO` |
| `BLOCKED_NAMES` | Protected file and folder names |
| `SKIP_DIRS` | Folders the search tools ignore |
| `MAX_FIND_RESULTS`, `MAX_SEARCH_RESULTS`, `MAX_LINE_CHARS`, `MAX_SEARCH_FILE_BYTES` | Search output limits |
| `MAX_WRITE_CHARS` | Largest file `write_file` will create |
| `RG_TIMEOUT_SECONDS` | Timeout for ripgrep |

## Testing

```bash
pytest -v
```

Tests run offline. The loop tests use a scripted fake model, and the provider tests use a fake Gemini client. Two real-call tests skip themselves when no API key is set.

## Build plan

The project follows a fixed order, each step with its own tests:

1. Provider, then the loop with a single read tool
2. Remaining tools, with the guard added as soon as the first path-taking tool exists
3. The verify step (run tests after edits)
4. MCP and the pull request flow
5. Memory
6. Logging, evals, README, demo

## Design rules

1. One door for side effects: every tool call passes through the guard.
2. Tools return strings or error text, they never crash the loop.
3. The provider is swappable: only `provider.py` imports the vendor SDK.
4. Prompts and config live outside the logic, so behavior can be tuned without editing code.
5. Everything is logged, because an invisible failure cannot be fixed.
6. Evals run after every change.

## Notes

- The model provider started as OpenRouter and moved to the Gemini API. Switching back only touches `provider.py`.
- The search tools depend on ripgrep, which respects `.gitignore` by default.