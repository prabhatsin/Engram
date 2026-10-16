import pytest
from engram import provider, config
from types import SimpleNamespace
def test_empty_prompt():
    with pytest.raises(provider.ProviderError):
        provider.ask("")

def test_whitespace_prompt():
    with pytest.raises(provider.ProviderError):
        provider.ask("   ")

def test_missing_key(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", None)
    with pytest.raises(provider.ProviderError):
        provider.ask("hi")

#! monkeypatch is a built-in pytest helper that temporarily changes something for the duration 
#! of one test

#?Why not just delete the key from .env? 
# Tests shouldn’t depend on or modify your real files. monkeypatch gives you a clean fake state, 
# and no real API call is ever made.

#--------------------------------------------------------------------------------------


#! NOTE: The fake_client helper replaces the real Gemini client, so these tests run offline and instantly. We’ll reuse it for the retry tests

def fake_client(response):
    models = SimpleNamespace(generate_content=lambda **kw: response)
    return SimpleNamespace(models=models)

def test_empty_response(monkeypatch):
    resp = SimpleNamespace(text=None, prompt_feedback=None, candidates=[])
    monkeypatch.setattr(provider, "get_client", lambda: fake_client(resp))
    with pytest.raises(provider.ProviderError):
        provider.ask("hi")

def test_blocked_response_reports_reason(monkeypatch):
    fb = SimpleNamespace(block_reason="SAFETY")
    resp = SimpleNamespace(text=None, prompt_feedback=fb, candidates=[])
    monkeypatch.setattr(provider, "get_client", lambda: fake_client(resp))
    with pytest.raises(provider.ProviderError, match="SAFETY"):
        provider.ask("hi")

def test_normal_response(monkeypatch):
    resp = SimpleNamespace(text="hello", prompt_feedback=None, candidates=[])
    monkeypatch.setattr(provider, "get_client", lambda: fake_client(resp))
    assert provider.ask("hi") == "hello"

# Leanring
#pytest only counts functions whose names start with test_.

