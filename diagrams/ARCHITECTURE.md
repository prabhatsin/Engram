# Engram: content removed from the README (parked)

Everything below was cut from the README during the restructure. It is kept verbatim for a future `docs/ARCHITECTURE.md` or similar.

---

## Intro paragraph (process note)

Engram is built layer by layer. Each layer is finished, hardened and tested before the next one starts. This README covers what exists today and what is planned.

## Status

| Layer | What it is | Status |
|---|---|---|
| 1. Provider | Gemini client with retries, timeouts, clear errors | Done |
| 2. Agent loop + tools | The think, act, observe cycle and the local tools | Done |
| 3. MCP / GitHub | Read issues and PRs, comment, open PRs through the GitHub MCP server | Done |
| 4. Memory (Mem0) | Per-repo facts recalled at chat start, saved at exit | Done |
| 5. Terminal UI | Rich-based output, decoupled from the loop through hooks | Done |
| 6. Production hardening | Context trimming, logging, evals, streaming | Planned |

Layer 1 detail:

| Piece | What it does | Status |
|---|---|---|
| Retries and backoff | Retries temporary API failures with increasing delay | Done |
| Timeouts | Every model call has a time limit | Done |
| Clear errors | All failures surface as one `ProviderError` | Done |
| Swappable | Only `provider.py` imports the vendor SDK | Done |

Layer 2 detail:

| Piece | What it does | Status |
|---|---|---|
| Agent loop | Runs tools until the model gives a final answer; step limit, stops on repeated identical failures | Done |
| Chat mode | Multi-turn conversation; agent can ask questions and take follow-ups; Ctrl+C cancels only the current turn | Done |
| Turn rollback | A failed or cancelled turn leaves the conversation history unchanged | Done |
| read_file | Reads text files; rejects directories and binary files | Done |
| find_files / search_text | ripgrep-based search, capped results, skips secrets and junk dirs | Done |
| write_file | Creates files; overwrite needs explicit flag and a fresh read; atomic write | Done |
| edit_file | Exact-match replace; needs a fresh read; handles CRLF; atomic write | Done |
| bash | Repo-root only, stripped env, timeout, capped output, denylist, y/N approval | Done |
| Path guard | Blocks paths outside the repo and protected files (.env, .git) | Done |
| Large-file paging | Truncation and line ranges for read_file | Deferred |

## How it works

```
 chat start                                          chat exit
 ----------                                          ---------
 [Memory] recall facts for this repo                 [Memory] scrub secrets,
 [GitHub MCP] connect, list tools                      save new facts
        |                                                   ^
        v                                                   |
User message --> [Agent loop] <------------------------------+
                     |
          system prompt + recalled notes + history
                     |
                     v
               [Provider] --> Gemini
                     |
         text reply or tool call?
            |                  |
          done          [Validate args + Guard]
        (show answer)          |
                      [Approval: bash, GitHub writes]
                               |
                       [Tool executor] ---------+
                   local tools / GitHub MCP     |
                               |                |
                        result goes back <------+
                        to the model

Hooks report every step to the Rich terminal UI. The loop never prints.
```

The loop is small on purpose. It calls the model, checks the request, runs the tool and feeds the result back, until the model replies in plain text. All the reliability comes from the pieces around it: the guard, the approval prompts, the limits and the rollback. Memory and GitHub plug in at the edges (start and exit, and as extra tools), so the loop itself does not change.

## Components

| Component | Responsibility |
|---|---|
| `provider` | Talks to the LLM. Retries, timeouts, one error type (`ProviderError`). Hides the vendor behind two functions: `generate_text` and `chat`. |
| `loop` | The cycle, plus limits and stop conditions. Tool failures go back to the model as text. Reports progress through hooks and never prints. |
| `tools` | Each tool is a name, a description, a Pydantic argument model and a Python function. |
| `registry` | The list of tools, looked up by name. Builds the declarations sent to the model. |
| `guard` | Resolves every path argument and blocks anything outside the repo or in a protected location. |
| `session` | Remembers which files were read this run, so edits can require a prior, fresh read. |
| `approval` | Asks the user y/N before bash commands and GitHub write actions. |
| `ui` | Rich terminal output (banner, tool steps, answers, errors, `/memory` table), driven by the loop's hooks. |
| `memory` | Mem0 store, one per repo. Recalls facts at chat start, saves new ones at exit, and scrubs secrets first. |
| `mcp` | Connects to the GitHub MCP server and converts its tools into Engram's tool format. Read tools are exposed directly, two write tools ask first, dangerous tools are never exposed. |
| `context` | Trims long tool output and summarizes old history (planned). |
| `config` | Model name, limits, protected names, all in one place. |

## Directory structure

```
engram/
├── src/engram/
│   ├── main.py          # CLI entry point, chat loop, memory and GitHub wiring
│   ├── loop.py          # agent loop and hooks
│   ├── provider.py      # LLM client
│   ├── config.py        # settings and limits
│   ├── guard.py         # path rules
│   ├── session.py       # read tracking
│   ├── approval.py      # y/N confirmation
│   ├── ui.py            # Rich terminal UI
│   ├── context.py       # history trimming (planned)
│   ├── tools/
│   │   ├── tool.py      # tool format and declaration builder
│   │   ├── registry.py  # tool lookup
│   │   ├── read.py
│   │   ├── write.py
│   │   ├── edit.py
│   │   ├── search.py    # find_files, search_text (ripgrep)
│   │   └── bash.py
│   ├── mcp/
│   │   ├── github.py    # sync client for the GitHub MCP server
│   │   └── tools.py     # converts MCP tools to Engram tools
│   ├── memory/
│   │   └── store.py     # Mem0 recall and remember, secret scrub
│   └── prompts/
│       └── system.md    # system prompt
├── tests/               # offline unit tests
├── evals/               # sample repos with seeded bugs (planned)
├── logs/                # run traces (planned, gitignored)
├── .env                 # keys (gitignored)
├── pyproject.toml
└── README.md
```

## Tools (full safeguards version)

| Tool | What it does | Key safeguards |
|---|---|---|
| `read_file` | Returns a text file's contents | Rejects directories and binary files. Records the read for later edits. |
| `find_files` | Finds files by glob | Skips junk folders, secrets and symlinks. Capped, sorted output. |
| `search_text` | Searches inside files, returns `file:line: text` | Plain text by default, regex opt-in. Skips big and binary files. Capped output. |
| `write_file` | Creates a new file | Refuses to overwrite unless asked. Overwriting needs a prior fresh read. Atomic write. |
| `edit_file` | Replaces exact text in an existing file | Needs a prior fresh read. Fails if the text is missing or matches more than once. Preserves line endings and permissions. |
| `bash` | Runs a shell command in the repo root | Timeout, output cap, stripped environment, denylist, y/N approval. |
| `github_*` (chat mode) | Reads repos, issues and PRs from GitHub | Read tools run directly. Issue and PR text is treated as data. |
| `github_create_pull_request`, `github_add_issue_comment` (chat mode) | Writes to GitHub | Ask the user y/N every time. |

## Reliability and guardrails (full version)

Engram is designed to fail safely, visibly and recoverably.

- **Errors go back to the model:** unknown tools, bad arguments, blocked paths and tool exceptions come back as text so the model can adapt. The loop never crashes on them.
- **Validated arguments:** every call is checked against the tool's Pydantic model before it runs. Unknown extra arguments are dropped.
- **One door for paths:** every path argument passes through the guard. Paths resolve before the check, so `..` tricks, symlinks and `./.env` retries are all caught.
- **Protected files:** `.env`, `.env.*` and `.git` are never readable or writable.
- **Edits need fresh reads:** a file must be read this run, and unchanged since, before it can be edited or overwritten.
- **Exact-match edits:** no whole-file rewrites for small changes, and ambiguous matches fail loudly.
- **Atomic writes:** a crash mid-write cannot leave a half-written file.
- **Bounded everything:** retries with backoff, request timeouts, capped tool output, a step limit, and a stop after repeated identical failures.
- **Turn rollback:** a failed or cancelled turn leaves the conversation history unchanged.
- **Human approval:** every bash command and every GitHub write asks y/N first. Dangerous GitHub tools (such as merge) are never exposed to the model.
- **Secrets stay out of memory:** messages that look like keys or passwords are dropped before anything is saved.
- **Prompt rules (not enforced by code):** the system prompt tells the agent to branch instead of committing on main, never merge, and treat issue, PR and remembered text as data, not instructions. Approval prompts are the backstop.

## MCP and GitHub (full version)

Engram connects to the remote GitHub MCP server, so the agent can read issues and pull requests and open a PR for its own fix. This is available in chat mode.

- Engram runs inside a local clone. Local tools do the editing, and MCP handles the GitHub side.
- The fix flow: read the issue through MCP, edit and test locally, commit on a new branch and push through git (each bash command asks first), then open the PR through MCP with `Closes #N` in the description. The agent never merges.
- Read tools are exposed automatically. Only two write tools exist (`create_pull_request`, `add_issue_comment`), and both ask before running. Everything else is hidden.
- MCP tools are converted into Engram's tool format with cleaned schemas, and their output is capped.
- Setup: create a fine-grained GitHub token with read and write access to Pull requests and Issues on the repos you want, and put it in `.env` as `GITHUB_TOKEN`. Without a token, chat mode runs with local tools only.

## Memory (full version)

Engram remembers facts about each repo across sessions, using Mem0.

- Stored locally in `~/.engram/memory` (embedded vector store plus a small SQLite history), with one memory scope per repo. Gemini does both the fact extraction and the embeddings, so no extra key is needed.
- At chat start, the most relevant facts for the repo are recalled and added to the system prompt, labeled as data and not instructions.
- At exit, the last part of the conversation is saved. Messages that look like secrets are removed first.
- `/memory` in chat shows what is stored for the current repo.
- Memory is best-effort: if saving or recalling fails, the chat carries on.

## Planned: production hardening (full version)

- **Context management:** truncate big tool outputs, summarize old turns when history gets long.
- **Logging:** a full trace of every step saved to `logs/`.
- **Evals:** 5 to 10 small tasks (a seeded bug in a sample repo) run after every change to catch regressions.
- **Memory quality:** save only user messages, let the user delete a note, and show newer notes over older ones.
- **Plan first for big tasks:** the agent writes a short plan, then executes step by step.
- **Fallback model** and optional streaming.
- **Large files:** `read_file` line ranges so the agent can page through big files.

## Known limits line removed

- One-shot mode has no memory and no GitHub tools; those are chat-mode only. (Now covered under Usage.)

## Configuration (config.py constants)

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
| `MEMORY_DIR` | Where Mem0 stores data (default `~/.engram/memory`) |
| `MAX_RECALL` | How many remembered facts go into the system prompt |
| `MAX_REMEMBER_MESSAGES` | How many recent messages are saved at exit |
| `MCP_START_TIMEOUT`, `MCP_CALL_TIMEOUT` | Timeouts for connecting to GitHub and for each GitHub call |
| `MAX_MCP_OUTPUT_CHARS` | Cap on a single GitHub tool result |

## Testing (full note)

Tests run offline. The loop tests use a scripted fake model, the provider tests use a fake Gemini client, and the memory and GitHub tests use fakes for Mem0 and the MCP server. Tests that need a real API key skip themselves when none is set.

## Build plan

The project was built in this order, each step with its own tests:

1. Provider, then the loop with a single read tool
2. Remaining tools, with the guard added as soon as the first path-taking tool exists
3. Chat mode, turn rollback and the terminal UI (through loop hooks)
4. Memory (Mem0)
5. GitHub through MCP, with approval on writes
6. Planned: context trimming, logging, evals, demo

## Design rules

1. One door for side effects: every path goes through the guard, and every risky action asks the user.
2. Tools return strings or error text, they never crash the loop.
3. The provider is swappable: only `provider.py` imports the vendor SDK.
4. The loop never prints: the UI listens through hooks, so the interface can change without touching the loop.
5. Prompts and config live outside the logic, so behavior can be tuned without editing code.
6. Text from outside (issues, PRs, remembered notes, files) is data, not instructions.
7. Memory and GitHub are optional extras: if they fail, the agent still works.