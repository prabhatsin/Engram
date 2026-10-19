
#? What real agents do: the common pattern is keeping the schema next to the function and we are doingt same here 
#? keeping the function and schema together 

from pydantic import BaseModel,Field
from  .tool import make_tool
import os
from .. import session
class ReadArgs(BaseModel):
    path: str = Field(description="File path")## Field(description=...) attaches the explanation the model will read.


# This is the core / real functiomn that actually reads the file ,:

def read_file(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    if os.path.isdir(path):
        raise IsADirectoryError(f"'{path}' is a directory, not a file")
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        raise ValueError(f"'{path}' is not a UTF-8 text file (it looks binary)")
    if "\x00" in text:
        raise ValueError(f"'{path}' is not a text file (it contains null bytes)")
    session.mark_read(path)
    return text

## READ_FILE: the read_file tool, bundling what goes to LLM(via declaration) 
# (name, description, argument schema) plus (+) the function that actually runs it.
READ_FILE=make_tool(
    name='read_file',
    description="Read a text file and return its contents.",
    args_model=ReadArgs,
    func=read_file,
    path_fields=("path",),
)










#? Doubts whats this func=read_file ?? 

# func=read_file stores the real function inside the tool, so the separate name-to-function mapping 
# isn’t needed anymore
'''
Your old way (two places):

The schema had "name": "book_slot" (just a string).
tool_registry mapped that string to the function: "book_slot": book_slot.


New way (one place): 

the tool carries its own function, so the match is already made. read_file here has no 
parentheses, because you're passing the function itself (not calling it), the same as putting it as a value
in your old registry dict.

'''



#! Question : Whats the difference between tool and function ??

'''
A function is plain Python code that does the work. A tool is a function packaged so an LLM can use it.

=>Function (read_file(path)): opens a file and returns its text. Python can call it, but the model 
doesn't know it exists.

=>Tool (READ_FILE): the function plus what the model needs to use it: a name, a description of what 
it does, and a schema of its arguments.


'''
# A schema is a structured description of the shape of some data: what fields it has, what type each one is, and which are required.



# Field(description=...) attaches the explanation the model will read.

# Pydantic reads the class and generates a dict:
# parameters = ReadArgs.model_json_schema()   # <- generated, not typed

'''
earlier we used to manually type and create , now pydantic does it for us , reducing the chances of error

{
  "type": "object",
  "properties": {"path": {"type": "string", "description": "File path"}},
  "required": ["path"],
}
'''