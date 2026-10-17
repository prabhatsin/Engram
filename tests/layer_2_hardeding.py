
'''
Layer 2: what's left

Loop hardening (loop.py)

1.Step limit: code given, so confirm that 3 tests pass.
2.Unknown tool name: return an error message to the model.
3.Bad or missing arguments: validate with args_model and return the error to the model.
4.Tool exceptions (file not found and so on): catch them and return the error text to the model.
5.Repeated identical failing call: detect it and stop.
6.Provider errors mid-loop: stop with a clean message.

read_file hardening (tools/read.py)
7. File not found, a directory instead of a file, and binary files.
8. Huge files: truncate the output with a note.

Guard (guard.py)
9. Path check: block anything outside the repo folder, and call it before every tool runs.

Remaining tools
10. search (grep/glob), so the agent can find files in a big repo.
11. write_file.
12. edit_file: exact-match replace that fails if the text isn’t found or isn’t unique, and refuses files not read this session.
13. bash: timeout, output truncation, and an allowlist/denylist with confirmation.

Wrap-up
14. main.py: handle errors and Ctrl+C cleanly.
15. System prompt in prompts/system.md: tell the model how to work in a repo.
16. A scripted end-to-end test: read, edit, run the tests, then answer.

'''