import httpx
import pytest
from types import SimpleNamespace
from google.genai import errors
from engram import config, provider

def test_empty_prompt():
    with pytest.raises(provider.ProviderError):
        provider.generate_text("")

def test_whitespace_prompt():
    with pytest.raises(provider.ProviderError):
        provider.generate_text("   ")

def test_missing_key(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", None)
    with pytest.raises(provider.ProviderError):
        provider.generate_text("hi")

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
        provider.generate_text("hi")

def test_blocked_response_reports_reason(monkeypatch):
    fb = SimpleNamespace(block_reason="SAFETY")
    resp = SimpleNamespace(text=None, prompt_feedback=fb, candidates=[])
    monkeypatch.setattr(provider, "get_client", lambda: fake_client(resp))
    with pytest.raises(provider.ProviderError, match="SAFETY"):
        provider.generate_text("hi")

def test_normal_response(monkeypatch):
    resp = SimpleNamespace(text="hello", prompt_feedback=None, candidates=[])
    monkeypatch.setattr(provider, "get_client", lambda: fake_client(resp))
    assert provider.generate_text("hi") == "hello"
def test_finish_reason_reported(monkeypatch):
    cand = SimpleNamespace(finish_reason="MAX_TOKENS")
    resp = SimpleNamespace(text=None, prompt_feedback=None, candidates=[cand])
    monkeypatch.setattr(provider, "get_client", lambda: fake_client(resp))
    with pytest.raises(provider.ProviderError, match="MAX_TOKENS"):
        provider.generate_text("hi")
# Leanring
#pytest only counts functions whose names start with test_.



def flaky_client(errs, resp):
    calls = {"n": 0}
    def generate_content(**kw):
        calls["n"] += 1
        if calls["n"] <= len(errs):
            raise errs[calls["n"] - 1]
        return resp
    return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)), calls

OK = SimpleNamespace(text="hello", prompt_feedback=None, candidates=[])

def setup(monkeypatch, errs):
    client, calls = flaky_client(errs, OK)
    sleeps = []
    monkeypatch.setattr(provider, "get_client", lambda: client)
    monkeypatch.setattr(provider.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(config, "BASE_DELAY", 1)
    return calls, sleeps

def test_retries_then_succeeds(monkeypatch):
    calls, sleeps = setup(monkeypatch, [errors.APIError(503, {"message": "busy"})] * 2)
    assert provider.generate_text("hi") == "hello"
    assert calls["n"] == 3

def test_backoff_delays_double(monkeypatch):
    calls, sleeps = setup(monkeypatch, [errors.APIError(429, {"message": "slow down"})] * 2)
    provider.generate_text("hi")
    assert sleeps == [1, 2]

def test_gives_up_after_max_retries(monkeypatch):
    calls, sleeps = setup(monkeypatch, [errors.APIError(503, {"message": "busy"})] * 10)
    with pytest.raises(provider.ProviderError, match="Gave up"):
        provider.generate_text("hi")
    assert calls["n"] == config.MAX_RETRIES + 1

def test_no_retry_on_bad_request(monkeypatch):
    calls, sleeps = setup(monkeypatch, [errors.APIError(400, {"message": "bad"})] * 10)
    with pytest.raises(provider.ProviderError):
        provider.generate_text("hi")
    assert calls["n"] == 1
    assert sleeps == []

def test_timeout_is_retried(monkeypatch):
    calls, sleeps = setup(monkeypatch, [httpx.ReadTimeout("timed out")])
    assert provider.generate_text("hi") == "hello"
    assert calls["n"] == 2


needs_key = pytest.mark.skipif(not config.API_KEY, reason="no GEMINI_API_KEY set")

@needs_key
def test_real_call():
    reply = provider.generate_text("Reply with the single word: pong")
    assert isinstance(reply, str)
    assert reply.strip()

@needs_key
def test_invalid_key_fails_clearly_and_is_not_retried(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "this-is-not-a-real-key")
    sleeps = []
    monkeypatch.setattr(provider.time, "sleep", lambda s: sleeps.append(s))
    with pytest.raises(provider.ProviderError, match="API error"):
        provider.generate_text("hi")
    assert sleeps == []