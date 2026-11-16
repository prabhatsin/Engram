# Engram: System Design

The diagrams below use Mermaid, so they render on GitHub, in VS Code (with a Mermaid
extension) and in `system_design.html`, which opens in any browser.

---

## 1. High-level architecture

```mermaid
flowchart TB
    User([User in terminal])

    subgraph Entry["Entry layer"]
        PY["pyproject.toml<br/>engram = engram.main:main"]
        MAIN["main.py<br/>main() · chat() · run_chat()"]
        UI["ui.py<br/>RichHooks, banner, show_answer"]
    end

    subgraph Core["Agent core"]
        LOOP["loop.py<br/>run_agent() · execute_tool()"]
        PROV["provider.py<br/>chat() · call_with_retry()"]
        CFG["config.py<br/>.env, limits, REPO_ROOT"]
        PROMPT["prompts/system.md"]
    end

    subgraph ToolLayer["Tool layer"]
        REG["tools/registry.py<br/>TOOLS · get_tool · all_declarations · register"]
        TOOLDEF["tools/tool.py<br/>make_tool · declaration"]
        GUARD["guard.py<br/>check_args · resolve_in_repo"]
        SESS["session.py<br/>read mtimes (fresh-read check)"]
        APPR["approval.py<br/>ask() y/N"]
        READ["read.py"]
        SEARCH["search.py<br/>find_files · search_text"]
        WRITE["write.py"]
        EDIT["edit.py"]
        BASH["bash.py"]
    end

    subgraph Ext["Optional integrations (chat mode only)"]
        MCPC["mcp/github.py<br/>GitHubMCP client (thread + asyncio)"]
        MCPT["mcp/tools.py<br/>build_tools: MCP tools → Engram tools"]
        MEM["memory/store.py<br/>recall · remember · scrub"]
    end

    subgraph Outside["External services and resources"]
        GEM[(Gemini API)]
        GH[(GitHub MCP server<br/>api.githubcopilot.com/mcp)]
        QD[("Mem0 + Qdrant on disk<br/>~/.engram/memory")]
        RG[[ripgrep rg]]
        REPO[("Target git repo<br/>REPO_ROOT")]
    end

    User --> PY --> MAIN
    MAIN --> UI
    MAIN --> LOOP
    MAIN --> MCPC
    MAIN --> MEM
    CFG --> PROMPT
    LOOP --> PROV --> GEM
    LOOP --> REG
    LOOP --> GUARD
    REG --> TOOLDEF
    REG --> READ & SEARCH & WRITE & EDIT & BASH
    MCPC --> MCPT --> REG
    MCPC <--> GH
    MCPT --> APPR
    BASH --> APPR
    READ & WRITE & EDIT --> SESS
    SEARCH --> RG
    READ & SEARCH & WRITE & EDIT & BASH --> REPO
    MEM --> QD
    MEM --> GEM
    UI -.hooks.-> LOOP
```

**Layers in one line each**

| Layer | Files | Job |
|---|---|---|
| Entry | `main.py`, `ui.py` | Parse args, pick one-shot or chat mode, show output |
| Agent core | `loop.py`, `provider.py`, `config.py` | Think, act, observe cycle; talk to Gemini with retries |
| Tools | `tools/*`, `guard.py`, `session.py`, `approval.py` | Validated, path-guarded actions on the repo |
| Integrations | `mcp/*`, `memory/store.py` | GitHub tools and per-repo memory (chat mode only) |

---

## 2. Program lifecycle (what runs when you type `engram`)

```mermaid
flowchart TD
    A["engram ...args"] --> B["main.main(argv)"]
    B --> C{args given?}
    C -- yes --> D["One-shot mode<br/>loop.run_agent(prompt)"]
    D --> D2["show_answer() and exit 0<br/>(errors exit 1, Ctrl+C exits 130)"]
    C -- no --> E["chat()"]
    E --> F["connect_github()<br/>only if GITHUB_TOKEN is set"]
    F --> F1["GitHubMCP.start()"] --> F2["mcp.tools.build_tools()"] --> F3["registry.register(tools)"]
    E --> G["run_chat(transcript)"]
    G --> G1["session.reset()"]
    G1 --> G2["store.recall() → facts"]
    G2 --> G3["build_system(facts)<br/>system.md + remembered notes"]
    G3 --> H{{"REPL: input('> ')"}}
    H -- "/memory" --> H1["ui.show_memories(store.recall())"] --> H
    H -- "task" --> I["loop.run_agent(prompt, history, hooks, system)"]
    I --> J["ui.show_answer(answer)<br/>append to transcript"] --> H
    H -- "exit / Ctrl+D" --> K["finally: save_memory(transcript)<br/>store.remember(last 20) → store.close()"]
    K --> L["github.close()"]
```

---

## 3. One agent turn (`loop.run_agent`)

```mermaid
sequenceDiagram
    autonumber
    participant M as main.py
    participant L as loop.py
    participant R as registry.py
    participant P as provider.py
    participant G as Gemini API
    participant H as ui.RichHooks
    participant T as tool func

    M->>L: run_agent(prompt, history, hooks, system)
    L->>L: copy history, append user prompt
    L->>R: all_declarations()
    R-->>L: JSON schemas of every tool
    loop until text answer (max 25 steps)
        L->>H: on_model_start (spinner)
        L->>P: chat(history, declarations, system)
        P->>G: generate_content (retry 429/5xx, backoff 2s·2^n)
        G-->>P: response
        P-->>L: {text, tool_calls, content}
        L->>H: on_model_end
        L->>L: history.append(content)
        alt no tool_calls
            L-->>M: (text, history)
        else tool_calls present
            loop each tool_call
                L->>H: on_tool_call
                L->>L: execute_tool(tool_call)
                L->>T: tool["func"](**safe_args)
                T-->>L: {"result"} or {"error"}
                L->>H: on_tool_result
                L->>L: repeat-failure check (3 strikes → AgentError)
            end
            L->>L: history.append(function responses as role=user)
        end
    end
```

---

## 4. Tool execution pipeline (`loop.execute_tool`)

Every tool call, local or GitHub, passes through the same four gates.

```mermaid
flowchart LR
    TC["tool_call<br/>{name, args}"] --> A{"registry.get_tool(name)"}
    A -- None --> E1["error: Unknown tool"]
    A -- found --> B{"Pydantic<br/>args_model(**args)"}
    B -- ValidationError --> E2["error: Invalid arguments"]
    B -- ok --> C{"guard.check_args<br/>path_fields → resolve_in_repo"}
    C -- GuardError --> E3["error: Blocked<br/>(outside repo, .env, .git)"]
    C -- ok --> D["tool func(**safe_args)"]
    D -- exception --> E4["error: Tool failed"]
    D -- ok --> OK["result"]

    subgraph Inside tool funcs
        D1["read_file → session.mark_read"]
        D2["write/edit → needs fresh read (mtime) → atomic_write"]
        D3["bash → length cap → denylist → auto-approve or approval.ask → subprocess with stripped env, timeout, capped output"]
        D4["github_* write → approval.ask → client.call_tool"]
    end
    D --- D1 & D2 & D3 & D4
```

Errors are returned to the model as data, not raised, so the model can correct itself.
Only `AgentError` (step limit, repeated failure) and `ProviderError` stop a turn.

---

## 5. Module dependency graph (who imports whom)

```mermaid
flowchart LR
    main --> config & loop & provider & session & ui
    main --> store["memory/store"]
    main --> ghmcp["mcp/github"] & mcptools["mcp/tools"] & registry["tools/registry"]
    ui --> loop
    loop --> provider & config & guard & session & registry
    provider --> config
    guard --> config
    registry --> read & search & write & edit & bash & tool["tools/tool"]
    read --> tool & session
    search --> tool & config
    write --> tool & config & session
    edit --> tool & config & session & write
    bash --> tool & config & approval
    mcptools --> tool & approval
    ghmcp --> config
    store --> config
```

`config.py` is the leaf everything depends on. `context.py` and `provider_open_router.py`
are empty placeholders for planned work (history trimming, OpenRouter provider).

---

## 6. Data that moves through the system

| Data | Shape | Created in | Consumed by |
|---|---|---|---|
| `history` | list of `google.genai.types.Content` | `loop.run_agent` | `provider.chat` (sent to Gemini) |
| tool declaration | `{name, description, parameters}` | `tools/tool.declaration` | Gemini, via `provider.chat` |
| tool dict | `{name, description, args_model, func, path_fields, schema?}` | `make_tool` | `registry`, `execute_tool` |
| `tool_call` | `{name, args}` | `provider.chat` | `loop.execute_tool` |
| tool output | `{"result": ...}` or `{"error": ...}` | `execute_tool` | back to Gemini as a function response |
| `transcript` | `[{role, content}]` (plain text) | `main.run_chat` | `store.remember` at exit |
| facts | `list[str]` | `store.recall` | `main.build_system` → system prompt |
