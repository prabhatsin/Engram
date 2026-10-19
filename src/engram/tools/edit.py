import os
from pydantic import BaseModel, Field
from .. import config, session
from .tool import make_tool
from .write import atomic_write



class EditArgs(BaseModel):
    path: str = Field(description="File to edit, relative to the repo root. It must have been read first.")
    old_text: str = Field(description="Exact text to replace, including whitespace and indentation. Must match exactly one place unless replace_all is true.")
    new_text: str = Field(description="Text to put in its place. Use an empty string to delete old_text.")
    replace_all: bool = Field(default=False, description="Replace every occurrence of old_text. Defaults to false.")


def edit_file(path, old_text, new_text, replace_all=False):
    rel = os.path.relpath(path, config.REPO_ROOT)
    if not old_text:
        raise ValueError("old_text is empty. To create a file use write_file.")
    if old_text == new_text:
        raise ValueError("old_text and new_text are identical, so nothing would change")
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {rel}")
    if os.path.isdir(path):
        raise IsADirectoryError(f"'{rel}' is a directory, not a file")

    seen_mtime = session.read_mtime(path)
    if seen_mtime is None:
        raise ValueError(f"You have not read '{rel}' yet. Read it with read_file first, then edit it.")
    if os.stat(path).st_mtime_ns != seen_mtime:
        raise ValueError(f"'{rel}' changed since you read it. Read it again before editing.")

    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            raw = f.read()
    except UnicodeDecodeError:
        raise ValueError(f"'{rel}' is not a UTF-8 text file")

    crlf = "\r\n" in raw and "\n" not in raw.replace("\r\n", "")
    if crlf:
        text = raw.replace("\r\n", "\n")
        old_text = old_text.replace("\r\n", "\n")
        new_text = new_text.replace("\r\n", "\n")
    else:
        text = raw

    count = text.count(old_text)
    if count == 0:
        raise ValueError(
            f"old_text was not found in '{rel}'. It must match exactly, including whitespace. "
            "Read the file again and copy the text exactly."
        )
    if count > 1 and not replace_all:
        raise ValueError(
            f"old_text matches {count} places in '{rel}'. Include more surrounding lines to make it unique, "
            "or set replace_all=true."
        )

    result = text.replace(old_text, new_text) if replace_all else text.replace(old_text, new_text, 1)
    if crlf:
        result = result.replace("\n", "\r\n")
    atomic_write(path, result)
    session.mark_read(path)
    replaced = count if replace_all else 1
    return f"Edited {rel}: replaced {replaced} occurrence(s)"


EDIT_FILE = make_tool(
    name="edit_file",
    description="Edit an existing file by replacing exact text. Read the file with read_file first. Fails if the text is not found or matches more than once.",
    args_model=EditArgs,
    func=edit_file,
    path_fields=("path",),
)



'''
Behaviors worth knowing:

Unread files: refused, and a read that is out of date is refused too (the mtime check).
Not found or ambiguous: both fail loudly with a hint on how to fix the call, so a wrong edit can’t silently succeed.
CRLF files: a file that uses only \r\n line endings still matches the model’s \n text, and the endings are preserved when written back. A file with mixed endings is matched exactly as it is, with no conversion.
Writes: use the same atomic temp-file swap as write_file, so a crash can’t leave a half-written file.
Consecutive edits: work, because each successful edit refreshes the stored mtime.
'''