
'''
# Config in one place: API key, model name, retry count, timeout and delay all live in config.py.

# Missing key: raises a clear ProviderError instead of crashing on import.

# Empty or whitespace prompt: rejected before any API call is made.

# Empty or blocked responses: raise a clear error that includes the reason (e.g. SAFETY).

# Retries with exponential backoff: 429, 5xx, timeouts and network errors are retried, with a max attempts limit.

# No retry on permanent errors: a bad request or invalid key fails right away with a clear message.

# Timeout on every call: the agent cant hang forever.

# One error type: everything surfaces as ProviderError, so the loop only has to catch one thing.

# Tests: fake-client tests for each failure case, plus two real-call tests that skip themselves when no key is set.

'''

