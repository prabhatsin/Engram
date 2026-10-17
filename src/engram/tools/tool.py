
#! tool.py: defines what a tool is so every tool file is built the same wayand builds the part of it that gets sent to the LLM.

def make_tool(name, description, args_model, func):
    """Packs a tool's name, description, argument model and Python function into one dict."""
    return {
        "name": name,
        "description": description,
        "args_model": args_model,
        "func": func,
    }

# builds the model-facing part i.e what exactly goes inside the LLM
def declaration(tool):
    """# Builds the model-facing view of a tool (name, description, argument schema), leaving out the function."""
    schema=tool["args_model"].model_json_schema()
    schema.pop("title",None)
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)

    return {
        "name":tool["name"],
        "description":tool["description"],
        "parameters":schema,
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


'''