
# Layer 2 (loop + tools)

'''
Step limit in the loop
Repeated failing-call detection
read_file truncation for huge files and line ranges
bash tool (timeout, output cap, stripped env, denylist, confirmation)
main.py error handling and Ctrl+C
System prompt tuning in prompts/system.md
Scripted end-to-end test (read, edit, run tests, answer)
Remove the temporary [tool] print
'''
# Layer 3 (MCP / GitHub)
'''
Connect to the GitHub MCP server
Convert MCP tools into Engram's tool format
Run MCP tools through the guard and error handling
Branch, commit and push flow
Open a pull request through MCP
Issues: read and comment
Approval before push and PR
'''
# Layer 4 (memory)
'''
Mem0 wrapper
Recall at session start, injected into the system prompt
Save lessons at session end
Only save lessons from verified tasks
Reflection step
'''
# Layer 5 (production hardening)
'''
context.py: trim big outputs, summarize old history
Logging to logs/
Evals with seeded-bug repos
Plan-first for big tasks
Prompt-injection handling for issue and file text
Streaming (optional)
Fallback model (optional)
'''

# Other
'''
Verify step: run tests after edits
Work on a branch, never main
Secret scan before commit
Session save/resume
Demo recording
'''