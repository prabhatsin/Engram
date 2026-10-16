
#!Design rules that keep it reliable
'''
    One door for side effects: every tool call passes through the guard. Nothing bypasses it.
    Tools return strings, never crash: errors become text the model can read.
    Provider is swappable: the rest of the code never imports google.genai directly, only provider.py.
    Prompts and config live outside the code: you tune behavior without editing logic.
    Everything is logged: if you can’t see why it failed, you can’t fix it.
    Evals run after every change: this catches regressions.

'''