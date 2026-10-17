# agent loop

# The cycle, plus limits (max steps, repeat detection) and stop conditions

from google.genai import types
from . import provider
from .tools import registry

def run_agent(prompt):

    """The loop sends the conversation to Gemini; if the model asks for tools, it runs them, adds the 
    results to the history and asks again. It repeats until the model answers in plain text, and that 
    text is the final result."""

    #Start the history with the user’s prompt as the first message
    history = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    #get the list of every tool’s model-facing description
    declarations = registry.all_declarations()

    while True:
        result=provider.chat(history,declarations)
        #stores the model’s raw message,in history
        history.append(result["content"])
        if not result["tool_calls"]:
            return result["text"]
            # This breaks the loop as soon as we get the text

        tool_results=[]
        # tool_results is our own list. It collects the results of every tool that ran in this turn.
        for tool_call in result["tool_calls"]:
            # tool_call: A plain dict {"name": ..., "args": {...}}, built by us in provider.py from a function_call
            tool=registry.get_tool(tool_call["name"])
            tool_output=tool["func"](**tool_call["args"])
            tool_results.append(types.Part.from_function_response(
                name=tool_call["name"],response={"result":tool_output}
            ))
        history.append(types.Content(role="user",parts=tool_results))
        






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