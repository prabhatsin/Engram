# agent loop
# The cycle, plus limits (max steps, repeat detection) and stop conditions

from google.genai import types
from . import provider,config,guard,session
from .tools import registry
from pydantic import ValidationError
# from .import guard,session
import json

class AgentError(Exception):
    pass


def describe_validation_error(e):
    """
    It turns Pydantic's validation error into one readable sentence the model can act on, like path: Field 
    required, by listing each problem as “field name: what's wrong” and joining them with semicolons.

    """
    problems = []
    for err in e.errors():
        field = ".".join(str(p) for p in err["loc"]) or "arguments"
        problems.append(f"{field}: {err['msg']}")
    return "; ".join(problems)


def execute_tool(tool_call):
    """Runs one tool call safely. Always returns a dict: {"result": ...} or {"error": ...}."""
    tool=registry.get_tool(tool_call["name"])
    #! Handle unvalaible tools case 
    if tool is None:
        # turns the list into one string.This makes error message ready easily 
        names = ", ".join(registry.available_tool_names())
        return {"error": f"Unknown tool '{tool_call['name']}'. Available tools: {names}"}
    try:
        #! argument validation step
        args=tool["args_model"](**tool_call["args"])
        # this args is a pydantic object 
    except ValidationError as e:
        return {"error": f"Invalid arguments for '{tool['name']}': {describe_validation_error(e)}"}
    #---------------------# kal SUBAH AAKAR UNDERSTAND WHAT IS BELOW THIS LINE--------
    try:
        safe_args = guard.check_args(tool, args.model_dump())
    except guard.GuardError as e:
        return {"error": f"Blocked: {e}"}
    try:
        return {"result": tool["func"](**safe_args)}
    except Exception as e:
        return {"error": f"Tool '{tool['name']}' failed: {type(e).__name__}: {e}"}

#-------------------------#--------UI--------------------UI---------------------
#TODO:
#? Whqat exacly is hooks ???--------------
class Hooks:
    """Display callbacks. Defaults do nothing, so the loop runs fine without a UI."""
    def on_model_start(self, step): pass
    def on_model_end(self): pass
    def on_tool_call(self, name, args): pass
    def on_tool_result(self, name, output): pass


#-------------------------------UI-------------------------UI-------------------------

def run_agent(prompt,history=None,hooks=None,system=None):

    """The loop sends the conversation to Gemini; if the model asks for tools, it runs them, adds the 
    results to the history and asks again. It repeats until the model answers in plain text, and that 
    text is the final result."""

    hooks = hooks or Hooks()
    # copy the caller's history so a failed turn never touches it (free rollback)
    history = list(history or [])
    history.append(types.Content(role="user", parts=[types.Part(text=prompt)]))

    #get the list of every tool’s model-facing description
    declarations = registry.all_declarations()
    steps=0
    failure_counts = {}
    while True:
        if steps >= config.MAX_STEPS:
            raise AgentError(f"Stopped after {config.MAX_STEPS} steps without a final answer.")
        steps+=1
        # This try catch is when LLM call may fail mid_task , eg when gemini is down or rate limit or
        # retries run out
        hooks.on_model_start(steps)  #! UI--------
        try:
            result=provider.chat(history,declarations,system=system)
        except provider.ProviderError as e:
            raise AgentError(
                f"Model call failed at step {steps} ({steps - 1} completed): {e}"
            ) from e
        finally:
            hooks.on_model_end()      #! UI------------- # always runs: spinner stops on error and Ctrl+C too
        #stores the model’s raw message,in history
        history.append(result["content"])
        if not result["tool_calls"]:
            # This breaks the loop as soon as we get the text
            return result["text"],history
    
        tool_results=[]
        # tool_results is our own list. It collects the results of every tool that ran in this turn.
        for tool_call in result["tool_calls"]:
            # tool_call: A plain dict {"name": ..., "args": {...}}, built by us in provider.py from a function_call
            hooks.on_tool_call(tool_call["name"], tool_call["args"]) #!------------UI
            # print(f"[tool] {tool_call['name']} {tool_call['args']}")
            tool_output = execute_tool(tool_call)
            hooks.on_tool_result(tool_call["name"], tool_output)  #!--------------- UI
            # # Stop the run if the exact same tool call (same name and arguments) keeps failing MAX_REPEATS 
            # times; a success resets the count.
            key = (tool_call["name"], json.dumps(tool_call["args"], sort_keys=True, default=str))
            if "error" in tool_output:
                failure_counts[key] = failure_counts.get(key, 0) + 1
                if failure_counts[key] >= config.MAX_REPEATS:
                    raise AgentError(
                        f"Stopped: '{tool_call['name']}' failed {config.MAX_REPEATS} times "
                        f"with the same arguments. Last error: {tool_output['error']}"
                    )
            else:
                failure_counts.pop(key, None)


            tool_results.append(types.Part.from_function_response(
                name=tool_call["name"],response=tool_output
            ))
        history.append(types.Content(role="user",parts=tool_results))
        




#? breking down the line "args=tool["args_model"](**tool_call["args"])"

'''
1. when the loop calls -> tool=registry.get_tool(tool_call["name"])

This tool is the whole tool defined in the (eg: read.py)
READ_FILE=make_tool(
    name='read_file',
    description="Read a text file and return its contents.",
    args_model=ReadArgs,
    func=read_file
) 
2. Now this this tool is dict containing args_model as well so when we do 

tool["args_model] we basically calling that defined pydantic class and 
putting (...) after it calls it, which creates an instance.

#! tool_call["args"]: the actual values the model sent this time. Different on every call, and not trusted yet

when we send it inside the inside the tool["args_model"]() 

'''

#! Summary:
'''
This feeds the model's values into your rules. ** unpacks {"path": "pyproject.toml"} into path="pyproject.toml". 
If the values fit the rules, you get a validated args object. If not, Pydantic raises ValidationError, 
which the except turns into an error message for the model.
'''





#! Learning : 
'''

Your old code: one function does everything. It holds the tools, builds the Gemini config, 
calls Gemini, reads function_call from the response, runs the tool, and loops. All Gemini-specific 
types (types.Tool, GenerateContentConfig, Part) are mixed into the loop.


The new design splits it in two:

Layer	                          Job
loop.py (the caller)	    owns the registry and schemas, decides which tools to offer, runs 
                            tools, repeats
provider.py (chat)	        talks to Gemini only: builds the config, makes the call, returns 
                             plain result

'''