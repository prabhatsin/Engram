import shutil
import subprocess
import pytest
from engram import config
from engram.tools import search
from engram.tools.search import find_files, search_text

pytestmark = pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep (rg) is not installed")


def write(root, rel, content="x"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ---- find_files ----

def test_find_by_extension(repo_root):
    write(repo_root, "a.py")
    write(repo_root, "b.txt")
    write(repo_root, "sub/c.py")
    assert find_files("*.py", str(repo_root)) == "a.py\nsub/c.py"

def test_find_with_path_pattern(repo_root):
    write(repo_root, "a.py")
    write(repo_root, "sub/c.py")
    assert find_files("sub/*.py", str(repo_root)) == "sub/c.py"

def test_find_no_match(repo_root):
    write(repo_root, "a.py")
    assert find_files("*.rs", str(repo_root)) == "No files matched."

def test_find_skips_junk_and_secrets(repo_root):
    write(repo_root, "a.py")
    write(repo_root, ".git/config")
    write(repo_root, "node_modules/x.js")
    write(repo_root, "__pycache__/a.pyc")
    write(repo_root, ".env")
    write(repo_root, ".env.local")
    assert find_files("*", str(repo_root)) == "a.py"

def test_find_is_sorted(repo_root):
    for name in ("c.txt", "a.txt", "b.txt"):
        write(repo_root, name)
    assert find_files("*.txt", str(repo_root)) == "a.txt\nb.txt\nc.txt"

def test_find_truncates(monkeypatch, repo_root):
    monkeypatch.setattr(config, "MAX_FIND_RESULTS", 2)
    for i in range(5):
        write(repo_root, f"f{i}.txt")
    out = find_files("*.txt", str(repo_root))
    assert out.splitlines()[:2] == ["f0.txt", "f1.txt"]
    assert "Showing the first 2" in out
    assert "f2.txt" not in out

def test_find_errors(repo_root):
    write(repo_root, "a.py")
    with pytest.raises(FileNotFoundError):
        find_files("*", str(repo_root / "nope"))
    with pytest.raises(NotADirectoryError):
        find_files("*", str(repo_root / "a.py"))
    with pytest.raises(ValueError, match="empty"):
        find_files("  ", str(repo_root))


# ---- search_text ----

def test_search_returns_file_and_line(repo_root):
    write(repo_root, "a.py", "x = 1\nfoo()\n")
    assert search_text("foo", str(repo_root)) == "a.py:2: foo()"

def test_search_is_literal_by_default(repo_root):
    write(repo_root, "a.py", "call foo(1)\n")
    assert search_text("foo(", str(repo_root)) == "a.py:1: call foo(1)"

def test_bad_regex_is_reported(repo_root):
    write(repo_root, "a.py", "foo")
    with pytest.raises(ValueError, match="Invalid regular expression"):
        search_text("foo(", str(repo_root), use_regex=True)

def test_search_regex(repo_root):
    write(repo_root, "a.txt", "foooo")
    assert search_text("fo+$", str(repo_root), use_regex=True) == "a.txt:1: foooo"

def test_search_ignore_case(repo_root):
    write(repo_root, "a.txt", "Foo")
    assert search_text("foo", str(repo_root)) == "No matches found."
    assert search_text("foo", str(repo_root), ignore_case=True) == "a.txt:1: Foo"

def test_search_file_glob(repo_root):
    write(repo_root, "a.py", "foo")
    write(repo_root, "b.txt", "foo")
    assert search_text("foo", str(repo_root), file_glob="*.py") == "a.py:1: foo"

def test_search_single_file(repo_root):
    write(repo_root, "a.py", "foo")
    write(repo_root, "b.py", "foo")
    assert search_text("foo", str(repo_root / "a.py")) == "a.py:1: foo"

def test_search_results_are_sorted(repo_root):
    write(repo_root, "b.txt", "foo")
    write(repo_root, "a.txt", "foo")
    assert search_text("foo", str(repo_root)) == "a.txt:1: foo\nb.txt:1: foo"

def test_search_binary_file_gives_no_plain_match(repo_root):
    (repo_root / "a.bin").write_bytes(b"\x00\x01foo\x00bar")
    out = search_text("foo", str(repo_root))
    assert "a.bin:1:" not in out

def test_search_skips_big_files(monkeypatch, repo_root):
    monkeypatch.setattr(config, "MAX_SEARCH_FILE_BYTES", 5)
    write(repo_root, "a.txt", "foo foo foo")
    assert search_text("foo", str(repo_root)) == "No matches found."

def test_search_survives_undecodable_bytes(repo_root):
    (repo_root / "a.txt").write_bytes(b"foo \xff\xfe")
    assert search_text("foo", str(repo_root)).startswith("a.txt:1: foo")

def test_search_truncates_long_lines(monkeypatch, repo_root):
    monkeypatch.setattr(config, "MAX_LINE_CHARS", 10)
    write(repo_root, "a.txt", "foo" + "b" * 200)
    out = search_text("foo", str(repo_root))
    assert out.startswith("a.txt:1:")
    assert "b" * 50 not in out

def test_search_caps_results(monkeypatch, repo_root):
    monkeypatch.setattr(config, "MAX_SEARCH_RESULTS", 2)
    write(repo_root, "a.txt", "foo\n" * 5)
    out = search_text("foo", str(repo_root))
    assert out.splitlines()[:2] == ["a.txt:1: foo", "a.txt:2: foo"]
    assert "Showing the first 2" in out
    assert "a.txt:3" not in out

def test_search_never_reads_secrets(repo_root):
    write(repo_root, ".env", "foo")
    write(repo_root, ".env.local", "foo")
    write(repo_root, ".git/config", "foo")
    assert search_text("foo", str(repo_root)) == "No matches found."

def test_search_errors(repo_root):
    with pytest.raises(FileNotFoundError):
        search_text("foo", str(repo_root / "nope"))
    with pytest.raises(ValueError, match="empty"):
        search_text("", str(repo_root))


# ---- ripgrep failure modes ----

def test_missing_ripgrep_is_reported(monkeypatch, repo_root):
    monkeypatch.setattr(search.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="not installed"):
        search_text("foo", str(repo_root))

def test_ripgrep_timeout_is_reported(monkeypatch, repo_root):
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired("rg", 1)
    monkeypatch.setattr(search.subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="timed out"):
        search_text("foo", str(repo_root))


# ---- symlinks ----

def test_symlinks_are_not_followed(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("foo")
    (repo / "link.txt").symlink_to(outside / "secret.txt")
    (repo / "linkdir").symlink_to(outside)
    (repo / "real.txt").write_text("foo")
    monkeypatch.setattr(config, "REPO_ROOT", repo.resolve())
    assert find_files("*", str(repo)) == "real.txt"
    assert search_text("foo", str(repo)) == "real.txt:1: foo"