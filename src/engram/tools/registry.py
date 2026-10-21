from .read import READ_FILE
from .search import FIND_FILES, SEARCH_TEXT
from .write import WRITE_FILE
from .edit import EDIT_FILE
from .tool import declaration
from.bash import BASH 

TOOLS = [READ_FILE, FIND_FILES, SEARCH_TEXT, WRITE_FILE,EDIT_FILE,BASH]


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


def available_tool_names():
    """Lists the avauilable tool names """
    return [tool["name"] for tool in TOOLS]




#--------------------------- added for mcp thing ----------------------

def register(tools):
    """Add tools (for example from MCP). A tool with an existing name replaces the old one."""
    for tool in tools:
        for i, existing in enumerate(TOOLS):
            if existing["name"] == tool["name"]:
                TOOLS[i] = tool
                break
        else:
            TOOLS.append(tool)

