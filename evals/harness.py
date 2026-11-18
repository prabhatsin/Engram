# Eval harness: runs one task against the real agent loop in a throwaway repo and records a trace.
#
# Nothing in src/ is changed. The harness wraps the agent from the outside:
#   - config.REPO_ROOT points at a fresh fixture repo per trial
#   - approval.ask is replaced by a scripted policy (no human at the keyboard)
#   - provider.call_with_retry is wrapped to count model calls, tokens and latency
#   - loop.Hooks records every tool call and its result (the trajectory)
# Everything is restored after each trial.

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from engram import approval, config, loop, provider, session  # noqa: E402
from engram.tools import registry  # noqa: E402


# --------------------------------------------------------------------------- task model

@dataclass
class Check:
    """One scored assertion about a run.
    kind: outcome (repo state), trajectory (tool calls), answer (final text), judge (LLM-graded).
    required=False checks are reported but don't decide pass/fail."""
    name: str
    fn: Callable  # fn(run) -> (bool, str)
    kind: str = "outcome"
    required: bool = True


@dataclass
class Task:
    id: str
    category: str
    prompt: object                      # str, or list[str] for multi-turn
    checks: list
    files: dict = field(default_factory=dict)     # path -> content of the fixture repo
    outside_files: dict = field(default_factory=dict)  # files next to (outside) the repo
    approve: str = "safe"               # approval policy: safe | all | none
    facts: list = None                  # remembered notes injected into the system prompt
    rubric: str = None                  # used by the LLM judge when --judge is on
    reference: Callable = None          # reference(workdir): applies a known-good solution
    setup: Callable = None              # setup(workdir): extra fixture prep after `git init`
    expect_error: bool = False          # True when stopping with AgentError is acceptable
    description: str = ""

    @property
    def prompts(self):
        return [self.prompt] if isinstance(self.prompt, str) else list(self.prompt)


# --------------------------------------------------------------------------- run record

@dataclass
class ToolEvent:
    turn: int
    name: str
    args: dict
    output: dict

    @property
    def ok(self):
        return "error" not in self.output

    @property
    def text(self):
        return str(self.output.get("result", self.output.get("error", "")))


@dataclass
class Run:
    task: Task
    trial: int
    workdir: Path
    answers: list = field(default_factory=list)
    tool_events: list = field(default_factory=list)
    approvals: list = field(default_factory=list)   # (command, approved)
    errors: list = field(default_factory=list)      # AgentError / ProviderError messages per turn
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model_seconds: float = 0.0
    seconds: float = 0.0
    snapshot: dict = field(default_factory=dict)    # rel path -> bytes, before the run
    results: list = field(default_factory=list)     # (Check, ok, detail)
    crash: str = None                               # harness or unexpected exception

    # --- convenience for checks
    @property
    def answer(self):
        return self.answers[-1] if self.answers else ""

    @property
    def all_answers(self):
        return "\n".join(a or "" for a in self.answers)

    def calls(self, name=None):
        return [e for e in self.tool_events if name is None or e.name == name]

    def bash_commands(self):
        return [e.args.get("command", "") for e in self.calls("bash")]

    def path(self, rel):
        return self.workdir / rel

    def read(self, rel):
        p = self.path(rel)
        return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None

    def current_files(self):
        return _snapshot(self.workdir)

    def changed_files(self):
        """Paths added, removed or modified compared with the fixture."""
        now = self.current_files()
        keys = set(now) | set(self.snapshot)
        return sorted(k for k in keys if now.get(k) != self.snapshot.get(k))

    def everything_model_saw(self):
        """All tool output text: whatever is here was sent to the model provider."""
        return "\n".join(e.text for e in self.tool_events)

    @property
    def passed(self):
        if self.crash:
            return False
        return all(ok for c, ok, _ in self.results if c.required)

    @property
    def score(self):
        scored = [ok for _, ok, _ in self.results]
        return sum(scored) / len(scored) if scored else 0.0


# --------------------------------------------------------------------------- fixtures

def _snapshot(root):
    out = {}
    for p in sorted(Path(root).rglob("*")):
        rel = p.relative_to(root)
        if not p.is_file() or rel.parts[0] == ".git" or "__pycache__" in rel.parts \
                or ".pytest_cache" in rel.parts:
            continue
        out[str(rel)] = p.read_bytes()
    return out


def _git(workdir, *args):
    subprocess.run(
        ["git", "-c", "user.email=evals@engram.local", "-c", "user.name=engram-evals", *args],
        cwd=workdir, check=True, capture_output=True,
    )


def build_fixture(task, base):
    """Create <base>/repo with the task's files, committed to a fresh git repo."""
    workdir = base / "repo"
    workdir.mkdir(parents=True)
    files = dict(task.files)
    # a root conftest.py makes `pytest` (not just `python -m pytest`) import repo modules
    if any(k.startswith("tests/") or "/test_" in k or k.startswith("test_") for k in files):
        files.setdefault("conftest.py", "")
    for rel, content in files.items():
        p = workdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    for rel, content in task.outside_files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    _git(workdir, "init", "-q")
    _git(workdir, "add", "-A")
    _git(workdir, "commit", "-q", "-m", "fixture", "--allow-empty")
    if task.setup:
        task.setup(workdir)
    return workdir


def run_pytest(workdir, *extra, timeout=120):
    """Run the fixture's tests with the eval's own Python. Returns (returncode, output)."""
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *extra],
        cwd=workdir, capture_output=True, text=True, timeout=timeout, env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


# --------------------------------------------------------------------------- approval policies

SAFE_COMMAND = re.compile(
    r"^\s*(python3?\s+-m\s+)?(pytest|git\s+(status|diff|log|show)|ls|pwd|cat|head|tail|wc)\b"
)


def make_approver(policy, run):
    """Stands in for the human answering y/N. Every request is recorded on the run."""
    def ask(command):
        if policy == "all":
            ok = True
        elif policy == "none":
            ok = False
        else:   # safe: what a careful reviewer would approve without thinking twice
            ok = bool(SAFE_COMMAND.match(command)) and not re.search(r"[;&|>]", command)
        run.approvals.append((command, ok))
        return ok
    return ask


# --------------------------------------------------------------------------- instrumentation

class _Patch:
    """Tiny monkeypatch: set attributes, restore them all on exit."""
    def __init__(self):
        self._saved = []

    def set(self, obj, name, value):
        self._saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def undo(self):
        for obj, name, value in reversed(self._saved):
            setattr(obj, name, value)
        self._saved.clear()


class RecordingHooks(loop.Hooks):
    def __init__(self, run):
        self.run = run
        self.turn = 0
        self._pending = None

    def on_tool_call(self, name, args):
        self._pending = (name, dict(args or {}))

    def on_tool_result(self, name, output):
        args = self._pending[1] if self._pending and self._pending[0] == name else {}
        self.run.tool_events.append(ToolEvent(self.turn, name, args, dict(output)))
        self._pending = None


def _wrap_provider(run, original):
    def call_with_retry(client, contents, gen_config=None):
        start = time.perf_counter()
        try:
            response = original(client, contents, gen_config)
        finally:
            run.model_seconds += time.perf_counter() - start
            run.model_calls += 1
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            run.input_tokens += getattr(usage, "prompt_token_count", 0) or 0
            run.output_tokens += (getattr(usage, "candidates_token_count", 0) or 0) + \
                (getattr(usage, "thoughts_token_count", 0) or 0)
        return response
    return call_with_retry


def build_system(facts):
    if not facts:
        return None
    from engram import main          # same prompt builder chat mode uses
    return main.build_system(facts)


# --------------------------------------------------------------------------- run one trial

def run_task(task, trial=0, keep=False, judge=None):
    """Run a task once and score it. Returns a Run."""
    base = Path(tempfile.mkdtemp(prefix=f"engram-eval-{task.id}-"))
    patch = _Patch()
    run = None
    try:
        workdir = build_fixture(task, base).resolve()
        run = Run(task=task, trial=trial, workdir=workdir, snapshot=_snapshot(workdir))
        hooks = RecordingHooks(run)
        patch.set(config, "REPO_ROOT", workdir)
        patch.set(approval, "ask", make_approver(task.approve, run))
        patch.set(provider, "call_with_retry", _wrap_provider(run, provider.call_with_retry))
        patch.set(registry, "TOOLS", list(registry.TOOLS))   # tasks never leak tool changes
        session.reset()

        system = build_system(task.facts)
        history = []
        start = time.perf_counter()
        for turn, prompt in enumerate(task.prompts):
            hooks.turn = turn
            try:
                answer, history = loop.run_agent(prompt, history, hooks=hooks, system=system)
                run.answers.append(answer or "")
                run.errors.append(None)
            except (loop.AgentError, provider.ProviderError) as e:
                run.answers.append("")
                run.errors.append(f"{type(e).__name__}: {e}")
        run.seconds = time.perf_counter() - start
        session.reset()
        score(run, judge=judge)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        if run is None:
            run = Run(task=task, trial=trial, workdir=base)
        run.crash = f"{type(e).__name__}: {e}"
    finally:
        patch.undo()
        if not keep:
            shutil.rmtree(base, ignore_errors=True)
    return run


def score(run, judge=None):
    checks = list(run.task.checks)
    if not run.task.expect_error:
        checks.insert(0, Check("finished without agent error",
                               lambda r: (not any(r.errors), "; ".join(e for e in r.errors if e) or "ok"),
                               kind="trajectory"))
    if judge and run.task.rubric:
        checks.append(Check("llm judge", lambda r: judge.grade(r), kind="judge"))
    for check in checks:
        try:
            ok, detail = check.fn(run)
        except Exception as e:
            ok, detail = False, f"check raised {type(e).__name__}: {e}"
        run.results.append((check, bool(ok), str(detail)))
    return run
