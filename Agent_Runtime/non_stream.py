
from google import genai
from dotenv import load_dotenv 
load_dotenv()
import os
import json
from Tools.registry import TOOLS
from Tools import (
                  write_file,
                   read_file,
                   execute_bash,
                   WRITE_FILE_SCHEMA,
                   READ_FILE_SCHEMA,
                   BASH_TOOL_SCHEMA
                   )

#!TODO: Do implement the general method for the message/history storage , not this SDK specific 'format'


def conversation_loop():
  API_KEY=os.getenv("GEMINI_API_KEY")
  client = genai.Client(api_key=API_KEY)
  history=[]
  while True:
      user_input=input("prompt: ")
      if user_input.lower()=='exit':
          break
    
      history.append(
                    {
                'type':'user_input',
                'content':[{'type':'text',
                            'text':user_input
                          }]
                }
                )
      # Defining another variable for the 
      function_calls=True
      while function_calls:
          response1 = client.interactions.create(
              model="gemini-3-flash-preview",
              store=False, 
              # By default, the API stores all Interaction objects (store=true) 
              # This line (store=False) tells that state in maintained by client i.e us not the server
              input= history,
              tools=[READ_FILE_SCHEMA,WRITE_FILE_SCHEMA,BASH_TOOL_SCHEMA],
          )
          # print(response1.model_dump())
          # print(response1)

          # print(response1.steps[-1].content[0].text)
          # response1_json=response1.model_dump()
          for step in response1.steps:
                print(step.model_dump())
                history.append(step.model_dump())
                # print(step)
                if step.type=='function_call':
                    print('function to call :',step.name)
                    print(f"arguments: {step.arguments}")
                    # checking if the called tool exist or not in the TOOLS dict
                    if step.name not in TOOLS:
                        result=f"The tool :{[step.name]} does not exist. Available tools are {list(TOOLS.keys())}"
                        is_error=True
                    else:
                        tool=TOOLS[step.name] # <-- LOOKUP
                        try:
                            result=tool(**step.arguments) # <-- EXECUTION
                            is_error=False
                        # Trying to handle the key error i.e what if key not present
                        except KeyError :
                            result=f"The tool{step.name} does not exist"
                            is_error=True
                        #Raised when a function is called with the wrong arguments 
                        except TypeError as e:
                            result=f"Invalid arguments for {step.name} :{e} tool"
                            is_error=True
                        except Exception as e:
                            result=f"Error {e} occured"
                            is_error=True

                    


                    print(result)
                    history.append(
                        {
                            "type":"function_result",
                            "name":step.name,
                            "call_id":step.id,
                            "result":[{"type":"text","text":json.dumps(result)}]
                        }
                    )
                    print("The result being fedback to llm is",result)

                else:
                    function_calls=False






# json.dump() vs json.dumps() ?? they are different ,remember



# if __name__=='__main__':
#     conversation_loop()








#! Learning 08 July

'''
Question : how don we know that whether the argument is right or wrong ?? in terms of number of arguments and datatype ?? 


Answer : Great question — these are actually two very different mechanisms, and Python only automatically catches one of them.

1. Argument count / names — Python checks this automatically

This is what **kwargs unpacking does at call time

It's not "before calling" — it's part of the call itself, split into two phases
When Python executes tool(**step.arguments), that call happens in two internal phases, in this order:

Phase 1 — Argument binding: Python takes the function's own def signature 
(the actual parameter names written in the source code — def write_file(path: str, data):) 
and tries to match every key in your step.arguments dict against those parameter names,
 filling each parameter slot.

Phase 2 — Body execution: Only if Phase 1 succeeds does Python actually start running the
 code inside the function (the with open(...), etc.).

#! 2.Argument data type — Python does NOT check this automatically

This is the part that surprises people. Look at your function signature:
pythondef write_file(path: str, data):
That : str next to path looks like it enforces "must be a string" — it does not. Python type hints are documentation only by default; nothing in the language actually checks them at runtime. So if the model sends:
pythonwrite_file(path="a.txt", data=12345)

— data being an int instead of a str — this call succeeds with no TypeError at all.
 It'll only blow up later, deep inside the function, when you actually try to do something string-like with data

So how do you actually catch bad types before calling the tool? 
You need explicit validation — this is exactly what #!validateToolArguments  was doing in the pi script you showed me.

Two common approaches:
i) Manual isinstance() checks against the tool's declared schema before calling.
ii) A validation library (e.g. pydantic) that takes your function's type hints and actually enforces them, raising a clear error if types don't match.

'''









# Before July 08

'''
How I'd structure the whole program

Without writing the full implementation, I'd organize it conceptually like this:

main()
│
├── Read API key
├── Create Gemini client
├── Create empty history
└── conversation_loop(client, history)

Then:

conversation_loop(client, history)
│
├── Get user input
├── Append user message to history
├── Send history to Gemini
├── Append returned steps
├── Print assistant response
└── Repeat


'''















#! Gemini SDK said this 
'''

"You must preserve and resend all model-generated 'steps'
(including thought and function_call steps)exactly as received."

'''


#! First, what is a "step"?
'''


A step is one event in the model's execution.

Think of an interaction as a sequence of events:



For an agent using tools you might get:

User Input

↓

Thought

↓

Function Call

↓

Function Result

↓

Thought

↓

Model Output

Each box in this sequence is a 'step'.


# ye sab ek ek step hain in the process of models execution
and we shouold preserve and append it inside the history 
when resending to model in the conversation loop 

'''








































#! Note


'''

What does ** do?

When you write

read_file(**arguments)

Python expands the dictionary into keyword arguments.

So this

arguments = {
    "path": "test_1.py"
}

read_file(**arguments)

becomes

read_file(path="test_1.py")

This is exactly what Gemini intended.


'''















'''

**kwargs — variable keyword arguments
Collects extra keyword arguments into a dict.

*args — variable positional arguments
Collects extra positional arguments into a tuple.

'''












'''
#?What exactly is model_dump()

"model_dump() converts the current Pydantic model instance, (i.e., the Python object and all of its fields)
 into a standard Python dictionary."


HTTP Response

        JSON

          │
          ▼

Interaction Object
(Pydantic BaseModel)

          │
          │ model_dump()
          ▼

Python Dictionary

          │
          │ json.dumps()
          ▼

JSON String


'''
#? Question Why the text output in two places i.e output_text and text (in steps) ???
#! NOTE : This output_text is just the textual output needed to sbhow to the user , 
#! For future references , if u want to play with the output or extract other elements 
# response.model_dump_json use karo and  extract steps wala part

'''
Imagine a future interaction

{
  "steps": [

    {
      "type":"thought"
    },

    {
      "type":"tool_call"
    },

    {
      "type":"tool_result"
    },

    {
      "type":"model_output",
      "content":[
        {
            "type":"text",
            "text":"Weather


'''










'''

#response is an object of type :Interaction

# Think of dir() as asking:

"Python, tell me EVERYTHING this object knows how to do and everything it contains."

#! Note When we see the sdk , waha pe jo response ka format diya hota hai 
# This is actually expected. You're comparing two different representations of the same object.

# The Gemini docs are showing the raw JSON response from the HTTP API, 
# while you're printing the Python SDK object.

# JO Rest wala output aayega the one we did using the that will be raw json , 
# But when we use the Python SDK , it will; be a python object

'''

'''

HTTP Server
      │
      ▼
Raw JSON
      │
      ▼
Google SDK
      │
      ▼
Interaction object



'''

'''
Server
   │
   ▼
JSON
{
   "status":"completed",
   "usage": {...}
}
   │
   │  SDK parses it
   ▼
Interaction(
    status='completed',
    usage=Usage(...),
    steps=[ThoughtStep(...)]
)







'''











'''

Analogy

Suppose the server returns:

{
  "name": "Prabhat",
  "age": 25
}

The SDK might internally do something like:

class User:
    def __init__(self, name, age):
        self.name = name
        self.age = age

So when you print it, you see

User(name='Prabhat', age=25)

instead of the original JSON.

The same thing is happening with Interaction.



'''