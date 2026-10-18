# Allow, deny or ask-the-user decisions, checked before every tool run

#! SAFETY CHECK 
'''
This is the first real safety rule. Before any tool runs, every path argument is resolved to an absolute 
path, and anything outside the repo folder, or any secrets file, is blocked.
'''

from pathlib import Path
from . import config

class GuardError(Exception):
    pass


def is_protected_name(name):
    return name in config.BLOCKED_NAMES or name.startswith(".env.")

#? why do we have .startswith ??? 
'''
BLOCKED_NAMES only matches exact names: .env and .git. It doesn't catch variants like .env.local, 
.env.production or .env.dev, which usually hold real secrets too. startswith(".env.") catches all of 
those, so the two checks cover different things.
'''
# NOTE This name blocking is bad or not effective way to handle , better ways are listed at the end of the script 

def resolve_in_repo(path):
    root = config.REPO_ROOT
    try:
        p = Path(path)
        if not p.is_absolute():
            p = root / p
        resolved = p.resolve()
    except (ValueError, OSError):
        raise GuardError(f"'{path}' is not a valid path")
    if not resolved.is_relative_to(root):
        raise GuardError(f"'{path}' is outside the repository folder")

    for part in resolved.relative_to(root).parts:
        if is_protected_name(part):
            raise GuardError(f"'{path}' is a protected file")
    return str(resolved)


def check_args(tool, args):
    checked = dict(args)
    for field in tool["path_fields"]:
        if field in checked:
            checked[field] = resolve_in_repo(checked[field])
    return checked







#? path_fileds
# path_fields on each tool says which of its arguments are file paths. read_file declares ("path",). 
# This tells the guard what to check, since it can’t guess which arguments are paths.


#? Alternative of path filed :

'''
Alternatives that avoid the extra list

Mark it in the Pydantic field: give path fields a special type or a marker (for example a RepoPath type 
that resolves and checks itself during validation). Then the class alone says which fields are paths, and 
path_fields disappears. It's neater, but a bit more advanced

'''

#? Unsolved Questions 

# 1. Why path_field added to tools/make_tool  ?? what is it didnwe had already a path argument ?
# I read this point number 2 on the claude chat ! 
# 2.Remember that this guard covers tools that declare path_fields. Every new tool (search, write, edit) 
# must declare its path arguments, or it bypasses the check. Bash is different, since a command can t
# ouch any path, so it gets its own rules later.




#! Big Limitation of this path thing : 

'''
Big limitation: a path guard doesn't protect you from the bash tool. A command like cat ~/.ssh/id_rsa bypasses 
it entirely. Real agents handle bash separately, with command approval, allow/deny lists, or an OS sandbox, so 
plan for that as your next safety layer.

'''


#! What are the general secure ways to do things ?? this name blocking doesnt seem defensive enough ?? 

'''
Real agents don't rely on a name blocklist. They layer several defenses, and the most important ones 
sit outside the model's control.

1.Permission prompts. Reads inside the workspace are usually allowed freely. Writes, shell commands and 
anything outside the workspace ask the user first, with allow/deny rules the user can configure. 
This is the main control.

2.OS-level sandboxing. Shell commands run in a sandbox (Seatbelt on macOS, Landlock/seccomp on Linux,
or containers) that restricts which folders can be written and usually blocks network access by default.
Even if the model is tricked, the operating system refuses. As I understand it, Codex CLI and Claude 
Code both offer this, though details change.

3.Secrets kept out of reach, not just hidden by name. Run the agent in a repo or container that doesnt 
have your real credentials, use short-lived or scoped API keys, and keep keys in the environment or a 
secrets manager instead of files in the project.

4.Network control. Block or allowlist outbound traffic, so even a leaked secret can't be sent to an 
attacker's server. This is what stops exfiltration after something goes wrong.

5.Prompt injection awareness. Content from files, web pages and tool output is treated as untrusted data, 
and actions it triggers need approval.

6.Audit and undo. Log every tool call, and work on a git branch so changes are reviewable and reversible.


'''

# For Engram, in order of value:

'''
# Keep the repo boundary guard (already done).
# Add an approval prompt for write, edit and bash.
# Run bash in a restricted environment (a Docker container is the easiest way to start).
# Don't point the agent at folders containing real secrets.

'''