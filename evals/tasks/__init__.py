# All eval tasks, grouped by category. Add a new suite by creating a module with TASKS and listing it here.

from . import behavior, capability, conversation, honesty, injection, safety

SUITES = [capability, behavior, honesty, conversation, safety, injection]
ALL = [t for suite in SUITES for t in suite.TASKS]

ids = [t.id for t in ALL]
assert len(ids) == len(set(ids)), "duplicate task ids"
