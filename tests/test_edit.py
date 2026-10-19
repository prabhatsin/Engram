import os
import pytest
from engram import session
from engram.tools import edit as edit_mod
from engram.tools.edit import edit_file
from engram.tools.read import read_file


def make(repo_root, name, content, read=True):
    f = repo_root / name
    f.write_text(content)
    if read:
        session.mark_read(str(f))
    return f


def test_replaces_single_occurrence(repo_root):
    f = make(repo_root, "a.txt", "hello world")
    out = edit_file(str(f), "world", "there")
    assert f.read_text() == "hello there"
    assert out == "Edited a.txt: replaced 1 occurrence(s)"

def test_unread_file_is_refused_and_untouched(repo_root):
    f = make(repo_root, "a.txt", "hello", read=False)
    with pytest.raises(ValueError, match="not read"):
        edit_file(str(f), "hello", "bye")
    assert f.read_text() == "hello"

def test_read_file_counts_as_reading(repo_root):
    f = make(repo_root, "a.txt", "hello world", read=False)
    read_file(str(f))
    edit_file(str(f), "world", "there")
    assert f.read_text() == "hello there"

def test_file_changed_since_read_is_refused(repo_root):
    f = make(repo_root, "a.txt", "hello")
    st = os.stat(f)
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    with pytest.raises(ValueError, match="changed since"):
        edit_file(str(f), "hello", "bye")
    assert f.read_text() == "hello"

def test_text_not_found(repo_root):
    f = make(repo_root, "a.txt", "hello")
    with pytest.raises(ValueError, match="not found"):
        edit_file(str(f), "nope", "x")
    assert f.read_text() == "hello"

def test_whitespace_must_match_exactly(repo_root):
    f = make(repo_root, "a.py", "def f():\n    return 1\n")
    with pytest.raises(ValueError, match="not found"):
        edit_file(str(f), "def f():\n  return 1", "x")

def test_multiple_matches_refused_and_untouched(repo_root):
    f = make(repo_root, "a.txt", "foo foo foo")
    with pytest.raises(ValueError, match="3 places"):
        edit_file(str(f), "foo", "bar")
    assert f.read_text() == "foo foo foo"

def test_replace_all(repo_root):
    f = make(repo_root, "a.txt", "foo foo foo")
    out = edit_file(str(f), "foo", "bar", replace_all=True)
    assert f.read_text() == "bar bar bar"
    assert "3 occurrence" in out

def test_replace_all_when_new_text_contains_old_text(repo_root):
    f = make(repo_root, "a.txt", "foo foo")
    edit_file(str(f), "foo", "foobar", replace_all=True)
    assert f.read_text() == "foobar foobar"

def test_identical_text_refused(repo_root):
    f = make(repo_root, "a.txt", "hello")
    with pytest.raises(ValueError, match="identical"):
        edit_file(str(f), "hello", "hello")

def test_empty_old_text_refused(repo_root):
    f = make(repo_root, "a.txt", "hello")
    with pytest.raises(ValueError, match="empty"):
        edit_file(str(f), "", "x")

def test_missing_file(repo_root):
    with pytest.raises(FileNotFoundError):
        edit_file(str(repo_root / "nope.txt"), "a", "b")

def test_directory(repo_root):
    (repo_root / "d").mkdir()
    with pytest.raises(IsADirectoryError):
        edit_file(str(repo_root / "d"), "a", "b")

def test_consecutive_edits_work(repo_root):
    f = make(repo_root, "a.txt", "one two")
    edit_file(str(f), "one", "1")
    edit_file(str(f), "two", "2")
    assert f.read_text() == "1 2"

def test_delete_text_with_empty_new_text(repo_root):
    f = make(repo_root, "a.txt", "keep remove keep")
    edit_file(str(f), " remove", "")
    assert f.read_text() == "keep keep"

def test_multiline_edit_keeps_indentation(repo_root):
    f = make(repo_root, "a.py", "def f():\n    x = 1\n    return x\n")
    edit_file(str(f), "    x = 1\n    return x", "    return 2")
    assert f.read_text() == "def f():\n    return 2\n"

def test_unicode(repo_root):
    f = make(repo_root, "u.txt", "नमस्ते दुनिया")
    edit_file(str(f), "दुनिया", "world")
    assert f.read_text(encoding="utf-8") == "नमस्ते world"

def test_crlf_file_matches_and_keeps_line_endings(repo_root):
    f = repo_root / "w.txt"
    f.write_bytes(b"a\r\nb\r\nc\r\n")
    session.mark_read(str(f))
    edit_file(str(f), "a\nb", "x\ny")
    assert f.read_bytes() == b"x\r\ny\r\nc\r\n"

def test_non_utf8_file_refused(repo_root):
    f = repo_root / "a.bin"
    f.write_bytes(b"\xff\xfe hello")
    session.mark_read(str(f))
    with pytest.raises(ValueError, match="UTF-8"):
        edit_file(str(f), "hello", "x")

def test_permissions_are_kept(repo_root):
    f = make(repo_root, "run.sh", "echo old")
    f.chmod(0o755)
    session.mark_read(str(f))
    edit_file(str(f), "old", "new")
    assert f.stat().st_mode & 0o777 == 0o755

def test_failed_write_keeps_original_and_leaves_no_temp_files(monkeypatch, repo_root):
    f = make(repo_root, "a.txt", "original")
    def boom(src, dst):
        raise OSError("disk exploded")
    monkeypatch.setattr(edit_mod.os, "replace", boom)
    with pytest.raises(OSError, match="exploded"):
        edit_file(str(f), "original", "new")
    assert f.read_text() == "original"
    assert sorted(os.listdir(repo_root)) == ["a.txt"]