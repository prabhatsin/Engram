# Mem0 Wrapper
# Recall at start, save lessons at end

"""Mem0 wrapper. The only file that imports mem0, so swapping it later touches only this file."""
import os
import logging
logging.getLogger("mem0").setLevel(logging.ERROR)   # hide spaCy/fastembed notices
from .. import config
os.environ.setdefault("MEM0_TELEMETRY", "False")   # before mem0 is imported anywhere
import re

_memory = None

class MemoryStoreError(Exception):
    pass


def _get():
    global _memory
    if _memory is None:
        from mem0 import Memory                    # lazy: no import cost unless used
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise MemoryStoreError("GEMINI_API_KEY is missing")
        path = str(config.MEMORY_DIR)
        _memory = Memory.from_config({
            "llm": {"provider": "gemini", "config": {
                "model": config.MODEL, "api_key": key, "temperature": 0.1}},
            "embedder": {"provider": "gemini", "config": {
                "model": config.EMBED_MODEL, "api_key": key,
                "embedding_dims": config.EMBED_DIMS}},
            "vector_store": {"provider": "qdrant", "config": {
                "path": path, "collection_name": "engram",
                "embedding_model_dims": config.EMBED_DIMS, "on_disk": True}},
            "history_db_path": os.path.join(path, "history.db"),
        })
    return _memory


def scope():
    """One memory space per repo."""
    return f"repo:{config.REPO_ROOT}"


def recall():
    """Stored facts for this repo, as a list of strings (at most MAX_RECALL)."""
    try:
        res = _get().get_all(filters={"user_id": scope()})
    except MemoryStoreError:
        raise
    except Exception as e:
        raise MemoryStoreError(f"recall failed: {type(e).__name__}: {e}") from e
    return [r["memory"] for r in res.get("results", [])][:config.MAX_RECALL]



#! This stops to save sectrets in the memory , .........

_SECRET = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|AKIA[0-9A-Z]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{20,}"
    r"|(api[_ -]?key|secret|password|passwd|token)\s*(is|=|:)\s*\S+)",
    re.I,
)

def scrub(messages):
    """Drop any turn containing something that looks like a secret,
    including the assistant reply to it."""
    out, skip_reply = [], False
    for m in messages:
        if m["role"] == "user":
            skip_reply = bool(_SECRET.search(m["content"]))
        if skip_reply or _SECRET.search(m["content"]):
            continue
        out.append(m)
    return out

#----------------------------------------------------------

def remember(messages):
    """Let Mem0 extract durable facts from [{"role", "content"}, ...]. No-op if empty."""
    messages = scrub(messages) # for check , 
    if not messages:
        return
    try:
        _get().add(messages, user_id=scope())
    except MemoryStoreError:
        raise
    except Exception as e:
        raise MemoryStoreError(f"save failed: {type(e).__name__}: {e}") from e

def close():
    """Close the vector store cleanly. Without this, Qdrant closes during
    interpreter shutdown and prints a noisy traceback."""
    global _memory
    if _memory is None:
        return
    try:
        _memory.vector_store.client.close()
    except Exception:
        pass                       # closing is best-effort; never crash on exit
    _memory = None