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
def call_with_retry(client, contents,gen_config=None):
    '''
    calls Gemini, retrying temporary failures, and raises ProviderError if it gives up
    or hits a permanent error.
    '''
    last_error = None
    #last_error remembers the most recent failure so we can report it at the end
    attempts = config.MAX_RETRIES + 1
    for attempt in range(attempts):
        try:
            return client.models.generate_content(model=config.MODEL, contents=contents,config=gen_config)
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
def chat(history, tools=None,system=None):
    #tools=None exists only so a plain "no-tools" call is also possible !

    if not history:
        raise ProviderError("History is empty.")
    client = get_client()
    # Build the request config. Attach tools only if some were provided by caller (loop)
    # The caller is the loop here 
    if tools:
        tool_config = [types.Tool(function_declarations=tools)]
    else:
        tool_config = None

    gen_config = types.GenerateContentConfig(
        tools=tool_config,
        system_instruction=system or config.SYSTEM_PROMPT)

    # Call Gemini (with retries on temporary failures).
    response = call_with_retry(client, history, gen_config)
    # Collect any tool calls the model asked for.
    function_calls = response.function_calls
    if function_calls is None:
        function_calls = []
    # Read text only when there are no tool calls (avoids an SDK warning).
    if function_calls:
        text = None
    else:
        text = response.text
    has_text = bool(text and text.strip())
    # Empty only if the model gave neither text nor tool calls.
    # (Empty text alone is fine, since a tool-call reply has no text.)
    if not has_text and not function_calls:
        reason = None
        # Find out why: blocked prompt first, then the finish reason
        if response.prompt_feedback:
            reason = response.prompt_feedback.block_reason
        if not reason and response.candidates:
            reason = response.candidates[0].finish_reason
        raise ProviderError(f"Empty response from model (reason: {reason}).")

    # Convert each call into a plain dict: {"name": ..., "args": {...}}.
    tool_calls = [] # This list is used to simply collect list of dictsv with each dict having function name and args

    ## Convert each Gemini FunctionCall (name + args) into a plain {"name", "args"} dict.
    for function_call in function_calls:
        # function_call is Gemini's own FunctionCall object containing (tool name + args)
        if function_call.args is None:
            args = {}
        else:
            args = dict(function_call.args)
        tool_calls.append({"name": function_call.name, "args": args})

    return {
        "text": text,
        "tool_calls": tool_calls,
        "content": response.candidates[0].content,
        # content is only for storing, passed back to Gemini exactly as it arrived.
    }



# when the model decides to use a tool, its reply contains a part holding function_calls , It is the SDK’s shortcut that gathers all of them into a list.




#?Question: explore whats this content , when awe already have text and tool calls  and what exacly goes in the history ??


'''
When we want to merge into history whatever we got from the LLM text or tool_call we need it in the format 

{
"role":"model",
parts......

}

this we get from the "content": response.candidates[0].content

#! The Nesting is :
response
  └─ candidates[0]
       └─ content
            ├─ role = "model"
            └─ parts = [ Part(text="..."), Part(function_call=...), ... ]

'''

'''

=>Because text and tool_calls are your own simplified copies, and Gemini needs its original message 
format back in the history.

=>Format: history has to hold Gemini Content objects. A dict like {"name": "book_slot", "args": {...}} isn’t one, so you’d have to rebuild the Content and Part objects by hand.

=>Lost details: the raw message can carry things your dicts drop. The main one is thought signatures, which newer Gemini models attach to function calls and expect to see again on the next request. If you rebuild the message without them, the model can lose its reasoning context or the API can reject the request.

=>Mixed replies: a single reply can contain text and several tool calls in a specific order. Rebuilding from text and tool_calls can change that order.

'''
#! Summary
'''
So the split is: text and tool_calls are for your loops decisions (show the answer, or run these
 tools), and content is only for storing, passed back to Gemini exactly as it arrived.
'''









if __name__=='__main__':
    generate_text("Hey how are u")