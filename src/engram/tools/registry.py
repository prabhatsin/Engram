from .read import READ_FILE
from .tool import declaration

TOOLS=[READ_FILE]

# Its the lookup function : it takes a name string(sent by model) and returns the matching tool
def get_tool(name):
    """Find a tool by the name string the model sent. Returns None if not found."""
    for tool in TOOLS:
        if tool["name"]==name:
            return tool
    return None



def all_declarations():
    """Build the list of model-facing tool descriptions to send to Gemini."""
    result=[]
    for tool in TOOLS:
        result.append(declaration(tool))
    return result