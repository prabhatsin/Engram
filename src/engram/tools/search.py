import os
import shutil # standard library module used for high-level file and directory operations.
import subprocess
from pydantic import BaseModel, Field
from .. import config
from .tool import make_tool


def _rel(path):
    # Show paths relative to the REPO_ROOT, so results are short and readable.
    # Strip the REPO_ROOT prefix from 'path' (e.g. /home/you/repo/src/a.py -> src/a.py) to save tokens; the guard resolves it back later.
    return os.path.relpath(path, config.REPO_ROOT)


def _rg(args):
    """Run ripgrep from the repo root and return its stdout.
    Exit code 1 only means "no matches", so it is not an error."""
    rg = shutil.which("rg")
    if rg is None:
        raise RuntimeError("ripgrep (rg) is not installed on this machine")
    try:
        result = subprocess.run(
            [rg, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=config.REPO_ROOT,
            timeout=config.RG_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Search timed out after {config.RG_TIMEOUT_SECONDS}s. Narrow the path or pattern.")
    if result.returncode not in (0, 1):
        raise RuntimeError(f"ripgrep failed: {result.stderr.strip()}")
    return result.stdout



def _exclude_args():
    # Skip junk folders and secrets. "!" in an rg glob means "exclude".
    names = list(config.SKIP_DIRS) + list(config.BLOCKED_NAMES) + [".env.*"]
    return [f"--glob=!{name}" for name in names]


class FindArgs(BaseModel):
    pattern: str = Field(description="Glob pattern, e.g. '*.py' or 'tests/test_*.py'")
    path: str = Field(default=".", description="Folder to search, relative to the repo root. Defaults to the whole repo.")


def find_files(pattern, path="."):
    """Find files by name with a glob pattern, using ripgrep.
    Returns sorted repo-relative paths, capped at MAX_FIND_RESULTS."""
    if not pattern.strip():
        raise ValueError("pattern is empty")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Folder not found: {_rel(path)}")
    if not os.path.isdir(path):
        raise NotADirectoryError(f"'{_rel(path)}' is a file, not a folder")

    limit = config.MAX_FIND_RESULTS
    out = _rg(["--files", "--sort=path", f"--glob={pattern}", *_exclude_args(), "--", path])
    matches = [_rel(line) for line in out.splitlines()]

    if not matches:
        return "No files matched."
    result = "\n".join(matches[:limit])
    if len(matches) > limit:
        result += f"\n[Showing the first {limit} files. Narrow the pattern or path to see more.]"
    return result

class SearchArgs(BaseModel):
    query: str = Field(description="Text to look for")
    path: str = Field(default=".", description="File or folder to search, relative to the repo root. Defaults to the whole repo.")
    file_glob: str = Field(default="", description="Only search files whose name matches this glob, e.g. '*.py'. Empty means all files.")
    ignore_case: bool = Field(default=False, description="Match upper and lower case alike. Defaults to false.")
    use_regex: bool = Field(default=False, description="Treat the query as a regular expression instead of plain text. Defaults to false.")


def search_text(query, path=".", file_glob="", ignore_case=False, use_regex=False):
    """Search inside files with ripgrep. Returns 'file:line: text' lines, capped at MAX_SEARCH_RESULTS."""
    if not query:
        raise ValueError("query is empty")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Path not found: {_rel(path)}")

    args = [
        "--line-number",
        "--with-filename",
        "--no-heading",
        "--color=never",
        "--sort=path",
        f"--max-filesize={config.MAX_SEARCH_FILE_BYTES}",
        f"--max-columns={config.MAX_LINE_CHARS}",
        "--max-columns-preview",
        *_exclude_args(),
    ]
    if not use_regex:
        args.append("--fixed-strings")   # plain text, so "foo(" works
    if ignore_case:
        args.append("--ignore-case")
    if file_glob:
        args.append(f"--glob={file_glob}")
    args += ["-e", query, "--", path]

    try:
        out = _rg(args)
    except RuntimeError as e:
        if use_regex and "regex" in str(e).lower():
            raise ValueError(f"Invalid regular expression: {e}")
        raise

    hits = []
    for line in out.splitlines():
        file_part, lineno, text = line.split(":", 2)
        hits.append(f"{_rel(file_part)}:{lineno}: {text.strip()}")

    if not hits:
        return "No matches found."
    limit = config.MAX_SEARCH_RESULTS
    result = "\n".join(hits[:limit])
    if len(hits) > limit:
        result += f"\n[Showing the first {limit} matches. Narrow the query, path or file_glob to see more.]"
    return result



FIND_FILES = make_tool(
    name="find_files",
    description="Find files by name using a glob pattern. Returns paths relative to the repo root.",
    args_model=FindArgs,
    func=find_files,
    path_fields=("path",),
)

SEARCH_TEXT = make_tool(
    name="search_text",
    description="Search inside files for text. Returns matching lines as 'file:line: text'.",
    args_model=SearchArgs,
    func=search_text,
    path_fields=("path",),
)

