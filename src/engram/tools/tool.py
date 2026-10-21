
#! tool.py: defines what a tool is so every tool file is built the same wayand builds the part of it that gets sent to the LLM.

def make_tool(name, description, args_model, func, path_fields=(), schema=None):
    """Packs a tool's name, description, argument model and Python function into one dict.
    schema: optional ready-made JSON schema (used by MCP tools instead of args_model)."""
    tool = {
        "name": name,
        "description": description,
        "args_model": args_model,
        "func": func,
        "path_fields": path_fields,
    }
    if schema is not None:          # key only exists for MCP tools, so local tools are unchanged
        tool["schema"] = schema
    return tool


# builds the model-facing part i.e what exactly goes inside the LLM
def declaration(tool):
    """# Builds the model-facing view of a tool (name, description, argument schema), leaving out the function."""
    schema = tool.get("schema")
    if schema is None:
        schema = tool["args_model"].model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
            prop.pop("default", None)
    return {
        "name": tool["name"],
        "description": tool["description"],
        "parameters": schema,
    }








#! Question whats this pop part ?? in schema and scheme .get properties ????

'''
what happens is when we do  "schema=tool["args_model"].model_json_schema()" what is does is 

{
  "title": "ReadArgs",                      # added by Pydantic (class name)
  "type": "object",
  "properties": {
    "path": {
      "title": "Path",                      # added by Pydantic (field name)
      "type": "string",
      "description": "File path"
    }
  },
  "required": ["path"]
}

It add the the key "title" in two places so we remove it before passing to LLM because LLM function schema maynot have 
these unknown keys and it will reject it then ..  

# The logic is applied for default key word as well , thats why we pop default also !
'''

#? INTERVIEW QUESTION: 
# Why we even need read , write ,edit when we know bash can do all of it ??
'''
Dedicated tools give the agent narrow, validated, guardable actions, while bash is a powerful but 
unconstrained fallback, so I use tools for the common operations and gate(or control) bash separately.”

'''

#Secondary benefits:
'''
There are secondary benefits too: 
1:it's portable (bash behaves differently across Windows, Mac and Linux), 

2.and tool calls are easier to log and review than shell commands.
'''
