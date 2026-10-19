import sys

def ask(command):
    # If stdin isn't a terminal (pipe, cron, CI, tests), no one can answer the prompt, 
    # so refuse instead of hanging or auto-approving.
    if not sys.stdin.isatty():
        return False
    print(f"\nThe agent wants to run:\n  $ {command}")
    try:
        answer = input("Allow? [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")

# It shows you the exact command and waits for your answer.

# Default is no: only y or yes approves, and anything else, including just pressing Enter, declines.



'''

Every program starts with three streams: stdin (input), stdout (output) and stderr (errors). 
The operating system decides what each is attached to when the program starts:

Run in your terminal: stdin is attached to the terminal, which is your keyboard.
Run with echo y | python ...: stdin is attached to a pipe from another program.
Run from cron, CI or a test: stdin is usually a file, /dev/null, or nothing.

#! isatty() asks the OS “is this stream a terminal device?” (TTY comes from “teletype”).
#! It's a fact about the connection, not about who is behind it.

'''

# 1.Since We will be running the agent with terminal the stdin(input) becomes terminal : 
# so , isatty() pass is ignored , and program moves ahead ! 

