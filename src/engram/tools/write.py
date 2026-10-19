import os
import shutil
import tempfile
from pydantic import BaseModel, Field
from .. import config, session
from .tool import make_tool


class WriteArgs(BaseModel):
    path: str = Field(description="File path to write, relative to the repo root")
    content: str = Field(description="The full text to write to the file")
    overwrite: bool = Field(default=False, description="Replace an existing file. Only set true after reading the file, and only when replacing the whole file is what the user asked for. Never set it when creating a new file. Defaults to false.")
# This added later with edit file 
def atomic_write(path, content):
    parent = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".engram-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def write_file(path, content, overwrite=False):
    rel = os.path.relpath(path, config.REPO_ROOT)
    if len(content) > config.MAX_WRITE_CHARS:
        raise ValueError(
            f"Content is {len(content)} characters, over the {config.MAX_WRITE_CHARS} limit. Split it across several files."
        )
    if os.path.isdir(path):
        raise IsADirectoryError(f"'{rel}' is a directory, not a file")
    exists = os.path.exists(path)
    if exists:
        seen = session.read_mtime(path)
        if seen is None:
            raise ValueError(
                f"You have not read '{rel}' yet. Read it first so you know what you are replacing."
            )
        if os.stat(path).st_mtime_ns != seen:
            raise ValueError(f"'{rel}' changed since you read it. Read it again before overwriting.")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except (FileExistsError, NotADirectoryError):
        raise NotADirectoryError(f"A parent of '{rel}' is a file, not a folder")

    if not exists:
        with open(path, "x", encoding="utf-8", newline="") as f:
            f.write(content)
        session.mark_read(path)
        return f"Created {rel} ({len(content)} characters)"

    atomic_write(path, content)
    session.mark_read(path)
    return f"Overwrote {rel} ({len(content)} characters)"


WRITE_FILE = make_tool(
    name="write_file",
    description="Create a new text file with the given content. To change part of an existing file use edit_file. overwrite=true replaces a whole existing file and requires reading it first.",
    args_model=WriteArgs,
    func=write_file,
    path_fields=("path",),
)




#! Design decisions:
'''

New files: opened with mode "x" (create only), so it can never clobber a file that appeared between the check and the write.
Overwrites: written to a temp file and swapped in with os.replace, so a crash mid-write can’t leave a half-written file. The temp file is cleaned up if anything fails, and the original file’s permissions are kept.
newline="": the content is written exactly as given, with no line-ending changes.
Parent folders: created automatically, and they’re already inside the repo because the guard checked the full path. A path whose parent is a file gets a clear error.
Guard: .env, .git and anything outside the repo are blocked before this function runs, even for new files.

'''