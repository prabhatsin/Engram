import pytest
from engram import provider, config

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