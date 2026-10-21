# Engram

A lightweight terminal coding agent built from scratch in plain Python, with no agent framework. Point it at a git repository, give it a task in plain English, and it reads, searches, edits and tests code through a small set of guarded tools. It can also work with GitHub issues and pull requests through MCP, and it remembers facts about each repo across sessions.

<!-- Demo GIF goes here -->

## Features

- **Plain Python agent loop:** no framework, just a small think, act, observe cycle.
- **Guarded tools:** read, search, write, edit and run commands, all restricted to the repo.
- **You stay in control:** every shell command and every GitHub write asks y/N first.
- **GitHub through MCP:** read an issue, fix it locally, and open a PR. The agent never merges.
- **Per-repo memory:** remembers facts about each repo across sessions (Mem0).
- **Chat and one-shot modes:** Ctrl+C cancels only the current turn, and a failed turn leaves history unchanged.

## Installation

Requirements: Python 3.10 or newer, [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) on your PATH, and a Gemini API key.

```bash
git clone https://github.com/prabhatsin/engram.git
cd engram
python -m venv myenv
source myenv/bin/activate        # Windows: myenv\Scripts\activate
pip install -e .
```

This installs Engram and adds the `engram` command. Then create a `.env` file in the project root with at least your API key (see [Configuration](#configuration)):

```
GEMINI_API_KEY=your_key_here
```
## Usage

```bash
cd /path/to/your/repo
engram                                   # chat mode
engram "What does src/app.py do?"        # one-shot
```

- **Chat mode** keeps the conversation going, uses memory and GitHub tools, and supports `/memory`.
- **One-shot mode** runs a single task and exits. It has no memory and no GitHub tools.

Example tasks:

```
> Fix issue #12 and open a PR
> Add tests for the date parsing in utils.py and run them
> Where are API retries configured?
```


## Tools

| Tool | What it does | Safeguards |
|---|---|---|
| `read_file` | Reads a text file | Rejects directories and binary files |
| `find_files` | Finds files by glob | Skips junk folders and secrets, capped output |
| `search_text` | Searches inside files (ripgrep) | Skips big and binary files, capped output |
| `write_file` | Creates a new file | No overwrite without a fresh read, atomic write |
| `edit_file` | Replaces exact text in a file | Needs a fresh read, fails on ambiguous matches |
| `bash` | Runs a command in the repo root | Timeout, denylist, y/N approval |
| GitHub read tools (chat mode) | Read issues, PRs and repo files, e.g. `github_issue_read`, `github_pull_request_read` | Read-only, text treated as data, not instructions |
| `github_create_pull_request` (chat mode) | Opens a pull request | y/N approval every time |
| `github_add_issue_comment` (chat mode) | Comments on an issue | y/N approval every time |


## Safety

- **Repo-only access:** every path is resolved and checked, so the agent cannot reach outside the repo. `.env` and `.git` are never readable or writable.
- **Careful edits:** a file must be freshly read before it is edited, edits are exact-match, and writes are atomic.
- **Human approval:** every bash command and GitHub write asks y/N. Dangerous GitHub tools, such as merge, are never exposed.
- **Bounded runs:** timeouts, retries, capped output, a step limit, and a stop after repeated identical failures.
- **Outside text is data:** issue, PR and remembered text is never treated as instructions, and secrets are scrubbed before anything is saved to memory.

## GitHub (MCP)

In chat mode, Engram connects to the remote GitHub MCP server. It reads the issue, fixes and tests locally, pushes a new branch, and opens a PR with `Closes #N`.

To enable it, create a fine-grained GitHub token with read and write access to Pull requests and Issues, and add it to `.env` as `GITHUB_TOKEN`. Without a token, chat mode runs with local tools only.

## Memory

- Stored locally in `~/.engram/memory`, with a separate scope for each repo.
- Stored facts for the repo are recalled at chat start and new ones are saved at exit.
- Type `/memory` in chat to see what is stored for the current repo.

## Configuration

Set these in `.env`:

| Variable | Required | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Your Gemini API key |
| `ENGRAM_MODEL` | No | Model name to use |
| `ENGRAM_REPO` | No | Repo the agent works on (defaults to the current folder) |
| `GITHUB_TOKEN` | No | Enables GitHub tools in chat mode |

## Known limits

- Conversation history is not trimmed yet, so very long chats can hit the model's context limit.
- `read_file` has no line ranges yet, so very large files are hard to work with.
- `bash` is soft containment (approval prompt, denylist, timeout), not a sandbox.
- Search skips hidden files and respects `.gitignore`.
- Memory is add-only: if a fact changes, the old and new notes both stay. The secret filter is regex-based, so it is best-effort.
- Only one Engram process can use the memory store at a time.

## Future work

- Context management: trim large tool output and summarize old turns
- Run logs: a full trace of every step
- Evals: small seeded-bug tasks run after every change
- Line ranges in `read_file` for large files
- Better memory: delete notes, prefer newer facts over older ones

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

Tests run offline using fakes for the model, Mem0 and the MCP server.

## License

MIT