

#? An eval measures how well the LLM-driven system behaves; a test checks that your code does exactly 
#? what you wrote.



#! Tests (what you have mostly)

'''
# Deterministic: same input, same result, pass or fail.
# They check your code: read_file raises the right error, the guard blocks ../x, the loop handles a bad tool name.
# Usually use fake clients, so they're fast and free.
'''

#! Evals
'''
Run the real model on tasks and score the outcome, because LLM output varies between runs.
They check the model's behavior inside your agent: does it pick search_text instead of guessing a path? Does it recover from a tool error? Does it finish the task in a sensible number of steps?
The result is usually a rate, such as “solved 8 of 10 tasks”, not a single pass/fail. The same eval can pass today and fail tomorrow with no code change.
Scoring can be a plain check (did the file get created, does the answer contain X), or another LLM acting as a judge for fuzzy answers.
'''

# Where your real-LLM pytest runs fit

'''
If a pytest test calls the real Gemini, it's really an eval written in pytest. The difference is how 
you treat it. A real-LLM test that asserts exact wording will be flaky. Better to assert on outcomes 
(the right tool was called, the file content appears in the answer), run each case a few times, and 
track the pass rate.
'''

# Why both

'''
Tests protect against code regressions, and run on every change.
Evals protect against model or prompt regressions, such as changing the system prompt, swapping models, or adding a tool, and run occasionally because they cost money and time.

A good first eval for Engram is 5 to 10 small tasks (“find where chat is defined”, “read X and report Y”) with a simple automatic check for each.

'''

#? Question:
# Are there tools / measure to write evals ?? for the real agents ??LLM systems ??

'''
Eval frameworks

# Inspect AI (from the UK AI Security Institute): open source, built for agent evals with tool use, sandboxes and scorers. A good fit for a coding agent.
# OpenAI Evals and promptfoo: define test cases in config files and compare prompts or models. promptfoo is easy to start with.
# DeepEval and Ragas: pytest-style LLM metrics, with Ragas leaning toward RAG evaluation.
'''
# Tracing and observability platforms

'''
LangSmith, Langfuse, Braintrust, Arize Phoenix: record every run (prompts, tool calls, outputs), let 
you build datasets from real traces, and score runs over time. Langfuse and Phoenix can be self-hosted.
'''

# Agent and coding benchmarks (for the idea, and sometimes to run)

'''
SWE-bench (fix real GitHub issues) and Terminal-Bench show how coding agents are measured: a task, 
a sandbox, and an automatic check such as “do the repo's tests now pass?”
'''

# Ways to score

'''
# Code-based checks: did the file get created, does the output contain X, did the tests pass. 
Cheapest and most reliable, so use these first.

# LLM-as-judge: another model grades fuzzy answers against a rubric. Useful, but calibrate it 
against a few human-graded examples.

#Trajectory checks: did the agent call the right tools, avoid forbidden ones, and finish within N steps?
'''


#! For Engram, a lightweight start with no framework

'''

Make a evals/ folder with 5 to 10 tasks as data: a prompt, a small fixture repo, and a check function.
Run each task a few times against the real model and record pass rate, number of tool calls and tokens.
Print a table, and rerun it after changing the system prompt, model or tools.

'''
