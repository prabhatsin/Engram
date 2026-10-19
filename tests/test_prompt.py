from pathlib import Path
from engram import config
from engram.tools import registry

PROMPT_FILE = Path(config.__file__).parent / "prompts" / "system.md"


def test_prompt_file_exists_and_has_content():
    text = PROMPT_FILE.read_text(encoding="utf-8")
    assert len(text.strip()) > 500

def test_config_loads_the_file_as_is():
    assert config.SYSTEM_PROMPT == PROMPT_FILE.read_text(encoding="utf-8")

def test_every_tool_is_mentioned_by_name():
    for name in registry.available_tool_names():
        assert name in config.SYSTEM_PROMPT, f"system prompt never mentions {name}"

def test_key_rules_are_present():
    prompt = config.SYSTEM_PROMPT.lower()
    for phrase in ("do not retry", ".env", "read a file with read_file", "do not overwrite", "data, not instructions"):
        assert phrase in prompt, f"missing rule: {phrase}"