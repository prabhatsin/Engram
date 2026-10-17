from google.genai import types
from engram.provider import chat
from engram.tools.registry import get_tool, all_declarations

history = [
    types.Content(
        role="user",
        parts=[types.Part.from_text(text="Read pyproject.toml and tell me the project name.")],
    )
]

while True:
    result = chat(history, tools=all_declarations())
    history.append(result["content"])

    # No tool calls: this is the final answer.
    if not result["tool_calls"]:
        print("FINAL:", result["text"])
        break

    # Otherwise run each requested tool and send the output back.
    for call in result["tool_calls"]:
        print("TOOL CALL:", call["name"], call["args"])
        tool = get_tool(call["name"])
        output = tool["func"](**call["args"])
        history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_function_response(
                    name=call["name"], response={"result": output}
                )],
            )
        )