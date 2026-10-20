# settings and limits

# Model name, limits, allowlists, loaded from one place

import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("ENGRAM_MODEL", "gemini-3.8-flash")
# Means “use the ENGRAM_MODEL environment variable if it’s set, otherwise fall back to this default name.”
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30

BASE_DELAY=2


MAX_STEPS = 25
MAX_REPEATS = 3

from pathlib import Path

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text()


#---guard.py------------

from pathlib import Path

REPO_ROOT = Path(os.getenv("ENGRAM_REPO", os.getcwd())).resolve()
BLOCKED_NAMES = {".env", ".git"}

#-----search tool---

MAX_FIND_RESULTS = 200
MAX_SEARCH_RESULTS = 100
MAX_LINE_CHARS = 200
MAX_SEARCH_FILE_BYTES = 1_000_000  #1mb

SKIP_DIRS = {".git", "node_modules", "__pycache__", "myenv",  ".venv", "venv", ".pytest_cache"}

RG_TIMEOUT_SECONDS = 15

#-----------write tool-----------------

MAX_WRITE_CHARS = 200_000

#-------bash tool--------------------

BASH_TIMEOUT_SECONDS = 60
MAX_BASH_OUTPUT_BYTES = 10_000
MAX_COMMAND_CHARS = 5_000
BASH_ENV_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "TERM", "VIRTUAL_ENV", "PYTHONPATH")

# The first three are limits: how long a command may run, how much output is kept, and 
# how long the command text may be.

'''
BASH_ENV_KEYS is a whitelist of environment variables a command is allowed to see. Your load_dotenv() 
puts GEMINI_API_KEY into the agent's own environment, and a command like env or echo $GEMINI_API_KEY 
would otherwise print it. Commands get only these few variables.

'''

#--------------memory------------------

MEMORY_DIR = Path(os.getenv("ENGRAM_MEMORY_DIR", Path.home() / ".engram" / "memory"))
MAX_RECALL = 20                       # cap facts injected into the system prompt
EMBED_MODEL = "models/gemini-embedding-001"
EMBED_DIMS = 768

MAX_REMEMBER_MESSAGES = 20


#---------------------------

MCP_START_TIMEOUT = 20          # seconds to connect
MCP_CALL_TIMEOUT = 30           # seconds per tool call
MAX_MCP_OUTPUT_CHARS = 20000    # cap what goes back to the model