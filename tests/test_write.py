import os
import pytest
from engram import config
from engram.tools import write as write_mod
from engram.tools.write import write_file


def test_creates_new_file(repo_root):
    out = write_file(str(repo_root / "a.txt"), "hello")
    assert (repo_root / "a.txt").read_text() == "hello"
    assert out == "Created a.txt (5 characters)"

def test_creates_parent_folders(repo_root):
    write_file(str(repo_root / "x" / "y" / "a.txt"), "hi")
    assert (repo_root / "x" / "y" / "a.txt").read_text() == "hi"

def test_empty_content_is_allowed(repo_root):
    write_file(str(repo_root / "empty.txt"), "")
    assert (repo_root / "empty.txt").read_text() == ""

def test_unicode_content(repo_root):
    write_file(str(repo_root / "u.txt"), "नमस्ते")
    assert (repo_root / "u.txt").read_text(encoding="utf-8") == "नमस्ते"

def test_line_endings_are_preserved(repo_root):
    write_file(str(repo_root / "w.txt"), "a\r\nb\n")
    assert (repo_root / "w.txt").read_bytes() == b"a\r\nb\n"

def test_refuses_to_overwrite_by_default(repo_root):
    f = repo_root / "a.txt"
    f.write_text("original")
    with pytest.raises(FileExistsError, match="overwrite"):
        write_file(str(f), "new")
    assert f.read_text() == "original"

def test_overwrite_replaces_content(repo_root):
    f = repo_root / "a.txt"
    f.write_text("original")
    out = write_file(str(f), "new", overwrite=True)
    assert f.read_text() == "new"
    assert out.startswith("Overwrote a.txt")

def test_overwrite_keeps_permissions(repo_root):
    f = repo_root / "run.sh"
    f.write_text("old")
    f.chmod(0o755)
    write_file(str(f), "new", overwrite=True)
    assert f.stat().st_mode & 0o777 == 0o755

def test_no_temp_files_left_behind(repo_root):
    f = repo_root / "a.txt"
    f.write_text("old")
    write_file(str(f), "new", overwrite=True)
    assert sorted(os.listdir(repo_root)) == ["a.txt"]

def test_failed_overwrite_keeps_original_and_cleans_up(monkeypatch, repo_root):
    f = repo_root / "a.txt"
    f.write_text("original")
    def boom(src, dst):
        raise OSError("disk exploded")
    monkeypatch.setattr(write_mod.os, "replace", boom)
    with pytest.raises(OSError, match="exploded"):
        write_file(str(f), "new", overwrite=True)
    assert f.read_text() == "original"
    assert sorted(os.listdir(repo_root)) == ["a.txt"]

def test_directory_target(repo_root):
    (repo_root / "d").mkdir()
    with pytest.raises(IsADirectoryError):
        write_file(str(repo_root / "d"), "x", overwrite=True)

def test_parent_is_a_file(repo_root):
    (repo_root / "a.txt").write_text("x")
    with pytest.raises(NotADirectoryError, match="parent"):
        write_file(str(repo_root / "a.txt" / "b.txt"), "x")

def test_too_large(monkeypatch, repo_root):
    monkeypatch.setattr(config, "MAX_WRITE_CHARS", 5)
    with pytest.raises(ValueError, match="limit"):
        write_file(str(repo_root / "a.txt"), "123456")
    assert not (repo_root / "a.txt").exists()