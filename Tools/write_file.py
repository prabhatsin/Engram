
#! We will use this script to write any 'data' inside  a file given the path of the file
import os
BASE_DIR=os.getcwd() 
# We are assuming that we will be running the agent from  the project root 
# if not , then it will give the cwd of where ever the agent is run from and 'temp' will be created relative ton that 
TEMP_DIR=os.path.join(BASE_DIR,"temp")
os.makedirs(TEMP_DIR,exist_ok=True)

def write_file(path:str,data):
        full_path=os.path.join(TEMP_DIR,path)
        # This line extractts the directory name from the given path 
        parent=os.path.dirname(full_path)
        # Checks if parent is a dir or empy string , if dir then make that directory 
        if parent:
              # this like creates the directory , extracted by dirname
              # exist_ok=True means , move own if this dir already exist
              os.makedirs(parent,exist_ok=True)
        with open(full_path,'w',encoding='utf-8') as file:
            return file.write(data)



# Check what does gimini expects ?? if it does in terms of format 
WRITE_FILE_SCHEMA={
      "type": "function",
      'name':'write_file',
      'description': '''Writes text content to a file. Creates the 
      file if it does not already exist. Overwrites existing content 
      unless otherwise specified.''',
        'parameters':{
              "type":"object",
              "properties":{
              'path':{
                    'type':'string',
                    'description':"Absolute or relative path of the file."
              },

              'data':{
                    'type':'string',
                    'description': 'Text content that will be written to the file.'
              }
              }
        }
}








#!TODO: Implement in Future These are the things implemented in Pi code base write tool file , that are left
'''
1. Path traversal guard (do this next — security-critical)
2. 2. Type-check data before writing



3. Better success message (matches write.ts's return value)
Pi returns "Successfully wrote {n} bytes to {path}" — informative for the model, not just a raw int:

5. Cancellation / abort support (lower priority, only if your loop supports interruption)
write.ts checks signal.aborted before each step so a user hitting Ctrl+C mid-write


6. File mutation queue (lower priority — only matters with real concurrency)
withFileMutationQueue in Pi prevents two overlapping writes to the same file from racing.
If your agent loop calls tools one at a time, sequentially 

'''









#! Learning July 9 , 
# os.path.dirname(path) this extracts the directory from a path 
'''
os.path.dirname("src/utils/helper.py")  # -> "src/utils"
os.path.dirname("notes.txt")            # -> ""  

What dirname actually does — splitting a path into two pieces
A path like "data/logs/output.txt" is really two concepts glued together with a string:

the directory part: "data/logs"
the filename part: "output.txt"

# Checks if parent is a dir or empy string , if dir then make that directory 
if parent:
        # this like creates the directory , extracted by dirname
        # exist_ok=True means , move own if this dir already exist
        os.makedirs(parent,exist_ok=True)


'''


#? Question
#! Should thie file name write_file.py , function name write_file and the description inside schema 
#  be same , or different or can be same and different both ,and which is the better and convienent used in production

'''
#! Later for production use this architecture

Tools/

    write_file/
        implementation.py
        schema.py
        __init__.py

    read_file/
        implementation.py
        schema.py
        __init__.py

    execute_bash/
        implementation.py
        schema.py
        __init__.py

'''