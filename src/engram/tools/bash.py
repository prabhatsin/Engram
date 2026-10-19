

#Bash is the riskiest tool because the path guard can’t see inside a command string (cat ~/.ssh/id_rsa bypasses it).

# Every command passes four checks in order:
'''
1.Denylist: dangerous patterns (sudo, rm -r, git push --force, touching .env) are refused outright,
  with no prompt.

2.Allowlist: only plain, harmless commands (ls, pwd, pytest, git status) run without asking.

3.Confirmation: anything else asks you [y/N] in the terminal first.

4.soft containment: the command runs from the repo root with a timeout, no stdin, capped output, and a 
 stripped environment so GEMINI_API_KEY never reaches it.

'''

#!IMPORTANT:
#NOTE: The design admits its own limit: a denylist is a safety net, and the confirmation prompt 
#is the real boundary.

#? Explore in more detail
#Soft containment: the command runs from the repo root with a timeout, no stdin, capped output, and a 
#stripped environment so GEMINI_API_KEY never reaches it.

import re
import os
import signal
import subprocess
import tempfile
from pydantic import BaseModel, Field
from .. import approval, config
from .tool import make_tool

_ENV_FILE = r"(^|[\s/'\"=<>:])\.env(\.\w+)?(?=$|[\s/'\";&|<>)])"
_GIT_DIR = r"(^|[\s/'\"=<>:])\.git(?=$|[\s/'\";&|<>)/])"

# DENY_RULES is a list of (pattern, reason) pairs. Each pattern is a regular expression describing a 
# dangerous kind of command, and the reason is the human-readable label.

DENY_RULES = [
    (r"\b(sudo|doas)\b", "privilege escalation"),
    (r"\brm\b[^;&|]*\s(-[a-zA-Z]*[rR]|--recursive)", "recursive delete"),
    (r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z|da)?sh\b", "piping a download into a shell"),
    (r"\bgit\s+push\b.*(--force|\s-[a-zA-Z]*f)", "force push"),
    (r"\bgit\s+reset\s+--hard\b", "hard reset"),
    (r"\bgit\s+clean\b[^;&|]*\s-[a-zA-Z]*f", "git clean with force"),
    (r"\bmkfs(\.\w+)?\b", "formatting a disk"),
    (r"\bdd\b[^;&|]*\bof=", "raw disk write"),
    (r">\s*/dev/(sd|nvme|hd|disk)", "writing to a disk device"),
    (r"\b(shutdown|reboot|halt|poweroff)\b", "shutting down the machine"),
    (r":\(\)\s*\{", "fork bomb"),
    (r"\b(chmod|chown)\b[^;&|]*\s(-[a-zA-Z]*R|--recursive)", "recursive permission change"),
    (_ENV_FILE, "touches a protected file (.env)"),
    (_GIT_DIR, "touches a protected folder (.git)"),
]

# _DENY compiles each pattern once, up front, with IGNORECASE so SUDO is caught too.

_DENY = [(re.compile(p, re.IGNORECASE), why) for p, why in DENY_RULES]

# denied_reason(command) checks the command against every pattern and returns the reason of the first 
# match, or None if the command is clean. Later, run_bash will refuse the command when this returns 
# a reason.
def denied_reason(command):
    for pattern, why in _DENY:
        if pattern.search(command):
            return why
    return None


# Question: What it does: it decides which commands may run without asking you. The rule is strict: a 
# command is auto-approved only if it passes three checks, and failing any one means “ask the user.”

UNSAFE_CHARS = re.compile(r"[;&|<>`$(){}\\\"'*?~!#\n\r]")

SAFE_PREFIXES = [
    ("ls",), ("pwd",), ("pytest",),
    ("git", "status"), ("git", "diff"), ("git", "log"),
]


def is_auto_approved(command):
    """True only for a plain, single, harmless command. Anything with shell syntax needs confirmation."""
    if UNSAFE_CHARS.search(command):
        return False
    tokens = command.split()
    if not any(tuple(tokens[:len(p)]) == p for p in SAFE_PREFIXES):
        return False
    for tok in tokens[1:]:
        if tok.startswith(("/", "~")) or ".." in tok or tok.startswith("--output"):
            return False
    return True


def _env():
    # Only whitelisted variables reach the command, so GEMINI_API_KEY never does.
    env = {k: os.environ[k] for k in config.BASH_ENV_KEYS if k in os.environ}
    # No .pyc caching: fast same-size edits (a - b -> a + b) could otherwise run stale code.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _kill(proc):
    # Kill the whole process group, not just the shell, so background children die too.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def _read_output(out):
    """Read the output file without loading all of it. Keeps the start and the end, since failures are usually at the end."""
    size = out.tell()
    limit = config.MAX_BASH_OUTPUT_BYTES
    out.seek(0)
    if size <= limit:
        text = out.read().decode("utf-8", errors="replace")
    else:
        half = limit // 2
        head = out.read(half)
        out.seek(size - half)
        tail = out.read(half)
        omitted = size - 2 * half
        text = (
            head.decode("utf-8", errors="replace")
            + f"\n[... {omitted} bytes omitted ...]\n"
            + tail.decode("utf-8", errors="replace")
        )
    return text if text.strip() else "(no output)"


class BashArgs(BaseModel):
    command: str = Field(description="The shell command to run, from the repo root")


def run_bash(command):
    if not command.strip():
        raise ValueError("command is empty")
    if len(command) > config.MAX_COMMAND_CHARS:
        raise ValueError(f"command is longer than {config.MAX_COMMAND_CHARS} characters")
    reason = denied_reason(command)
    if reason:
        raise ValueError(f"Command refused: {reason}. Do not retry it in another form. Tell the user.")
    if not is_auto_approved(command) and not approval.ask(command):
        raise PermissionError(
            "The user declined to run this command. Do not retry it. Ask the user what to do instead."
        )
    with tempfile.TemporaryFile() as out:
        proc = subprocess.Popen(
            command,
            shell=True,
            executable="/bin/bash",
            cwd=config.REPO_ROOT,
            env=_env(),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        timed_out = False
        try:
            proc.wait(timeout=config.BASH_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill(proc)
        except BaseException:
            _kill(proc)
            raise
        text = _read_output(out)

    if timed_out:
        raise RuntimeError(
            f"Command timed out after {config.BASH_TIMEOUT_SECONDS}s and was killed. Output so far:\n{text}"
        )
    return f"exit code: {proc.returncode}\n{text}"

BASH = make_tool(
    name="bash",
    description=(
        "Run a shell command from the repo root, for example to run tests or check git status. "
        "Returns the exit code and output. A non-zero exit code is a normal result, so read the output. "
        "The user must approve most commands. If a command is refused or declined, do not retry it."
    ),
    args_model=BashArgs,
    func=run_bash,
)

