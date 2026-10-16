# NOTE: ROLE OF THE SCRIPT  IS , ??
# Talks to the LLM, handles retries and timeouts, and hides the vendor behind one interface

#!-------------------------------------------------------------------------

from google import genai
#This is a relative import. The dot (.) means “from the current package”, i.e. the same folder this file lives in.
from . import config


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
    return genai.Client(api_key=config.API_KEY)


def ask(prompt):
    ## Reject empty input: catches None, "", and whitespace-only prompts
    if not prompt or not prompt.strip():
        raise ProviderError("Prompt is empty.")
    client=get_client()
    response=client.models.generate_content(model=config.MODEL,contents=prompt)
    text =response.text
    if not text or not text.strip():
        reason=None
        if response.prompt_feedback:
            reason=response.prompt_feedback.block_reason
        if not reason and response.candidates:
            reason=response.candidates[0].finish_reason
        raise ProviderError(f"Empty response from model (reason: {reason}).")
    return text

