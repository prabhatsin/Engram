# NOTE: ROLE OF THE SCRIPT  IS , ??
# Talks to the LLM, handles retries and timeouts, and hides the vendor behind one interface

#!-------------------------------------------------------------------------

from google import genai
#This is a relative import. The dot (.) means “from the current package”, i.e. the same folder this file lives in.
from . import config
import time
import httpx
from google.genai import errors, types

# It is a custom exception: your own named error type.
# This makes a new class that inherits from Python’s built-in Exception. That inheritance is 
# what makes it raisable.
#?Why bother, instead of raising a plain Exception?
'''
1.The name tells you what kind of failure it is, and lets callers catch just that kind:
2 So the agent loop will later catch it and handle it cleanly, instead of crashing on whatever 
Gemini throws.
'''
class ProviderError(Exception):
    pass

def get_client():
    if not config.API_KEY:
        raise ProviderError("GEMINI_API_KEY is missing. Add it to your .env file.")
    return genai.Client(api_key=config.API_KEY,
    http_options=types.HttpOptions(timeout=config.TIMEOUT_SECONDS * 1000),
    # What it is: the request timeout, meaning how long to wait( in miliseconds because sdk expects miliseconds) 
    # for Gemini to answer a single call before giving up on that attempt.
    )


#!---------------------------------------------------------------------------
RETRYABLE_CODES = {429, 500, 502, 503, 504}
# The list of error codes worth retrying: rate limit (429) and server-side problems (5xx).
def call_with_retry(client, prompt):
    '''
    calls Gemini, retrying temporary failures, and raises ProviderError if it gives up
    or hits a permanent error.
    '''
    last_error = None
    #last_error remembers the most recent failure so we can report it at the end
    attempts = config.MAX_RETRIES + 1
    for attempt in range(attempts):
        try:
            return client.models.generate_content(model=config.MODEL, contents=prompt)
        except errors.APIError as e:
            if e.code not in RETRYABLE_CODES:
                raise ProviderError(f"API error {e.code}: {e.message}") from e
            last_error = e
        # It catches network-level failures: cases where the request never got a proper reply from Gemini at all.    
        except httpx.TransportError as e:
            last_error = e
        if attempt < attempts - 1:
            time.sleep(config.BASE_DELAY * 2 ** attempt)
    raise ProviderError(f"Gave up after {attempts} attempts: {last_error}")



#? Learning : We can have two kinds of API error one is missing api and other is wrong , expired or revoked !!

'''

=> if not config.API_KEY catches a key that is missing entirely (empty .env, typo in the variable 
name). It fails fast, before any network call, with a friendly message.

=> The APIError branch catches a key that is present but wrong, expired, or revoked. You only find that 
out when Gemini replies with a 400/401/403, so it can only be handled after the call.

'''

#!-----------------------------------------------------------------------------
def generate_text(prompt):
    '''
    takes in prompt and generates the text 
    '''

    ## Reject empty input: catches None, "", and whitespace-only prompts
    if not prompt or not prompt.strip():
        raise ProviderError("Prompt is empty.")
    client=get_client()
    response=call_with_retry(client,prompt)
    text =response.text
    # Same empty check as before: catches None, "", and whitespace-only replies.
    if not text or not text.strip():
        reason=None
        # If Gemini returns no text, find out why (blocked prompt or finish reason) and raise a clear error
        if response.prompt_feedback:
            reason=response.prompt_feedback.block_reason
        if not reason and response.candidates:
            reason=response.candidates[0].finish_reason
        raise ProviderError(f"Empty response from model (reason: {reason}).")
    return text


#? Blocked prompt and Finish reason
'''
# Blocked prompt (prompt_feedback.block_reason) ==> Before generation
Gemini refuses your input before generating anything. The model never even starts.

# Finish reason (candidates[0].finish_reason) ==> During generation
Here the prompt was accepted, the model started answering, and then it stopped. The reason is recorded here

SAFETY: the model began generating, but the answer itself crossed a safety line, so it was cut off.
MAX_TOKENS: you set a low output limit (say 50 tokens) and asked for a long essay. It stops mid-answer. In some cases you get little or no usable text.
RECITATION: the model was about to output text too close to copyrighted material, so it stopped.

''' 

if __name__=='__main__':
    generate_text("Hey how are u")