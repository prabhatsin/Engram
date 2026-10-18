import pytest
from engram import config, guard
from engram.guard import GuardError, resolve_in_repo
from engram.tools.tool import make_tool
from engram.tools.read import ReadArgs

def test_relative_path_inside_repo(repo_root):
    assert resolve_in_repo("src/a.py") == str(repo_root / "src" / "a.py")

def test_absolute_path_inside_repo(repo_root):
    p = str(repo_root / "a.txt")
    assert resolve_in_repo(p) == p

def test_repo_root_itself_is_allowed(repo_root):
    assert resolve_in_repo(str(repo_root)) == str(repo_root)

def test_dotdot_escape_blocked():
    with pytest.raises(GuardError, match="outside"):
        resolve_in_repo("../secret.txt")

def test_dotdot_that_stays_inside_is_fine(repo_root):
    assert resolve_in_repo("a/../b.txt") == str(repo_root / "b.txt")

def test_absolute_path_outside_blocked():
    with pytest.raises(GuardError, match="outside"):
        resolve_in_repo("/etc/passwd")

def test_sibling_folder_with_same_prefix_blocked(repo_root):
    with pytest.raises(GuardError, match="outside"):
        resolve_in_repo(str(repo_root) + "-evil/x.txt")

def test_symlink_escape_blocked(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("x")
    (repo / "link").symlink_to(outside)
    monkeypatch.setattr(config, "REPO_ROOT", repo.resolve())
    with pytest.raises(GuardError, match="outside"):
        resolve_in_repo("link/secret.txt")

@pytest.mark.parametrize("name", [".env", "sub/.env", ".env.local", ".git/config"])
def test_protected_files_blocked(name):
    with pytest.raises(GuardError, match="protected"):
        resolve_in_repo(name)

@pytest.mark.parametrize("name", ["env.py", "my.env", "dotenv/a.txt", "gitignore.txt"])
def test_similar_names_are_allowed(name, repo_root):
    assert resolve_in_repo(name) == str(repo_root / name)

def test_null_byte_blocked():
    with pytest.raises(GuardError, match="not a valid path"):
        resolve_in_repo("a\x00b")

def test_check_args_only_touches_path_fields(repo_root):
    tool = make_tool("t", "x", ReadArgs, lambda path: "", path_fields=("path",))
    out = guard.check_args(tool, {"path": "a.txt", "other": "../x"})
    assert out == {"path": str(repo_root / "a.txt"), "other": "../x"}

def test_tool_without_path_fields_is_unchanged():
    tool = make_tool("t", "x", ReadArgs, lambda path: "")
    assert guard.check_args(tool, {"path": "../x"}) == {"path": "../x"}