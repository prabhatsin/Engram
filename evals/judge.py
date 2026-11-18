# LLM-as-judge for fuzzy qualities (clarity, honesty of the summary) that code checks can't score.
# Use it on top of code checks, never instead of them, and calibrate it: hand-grade ~10 runs and
# compare (see README). The judge sees the task, rubric, trajectory and diff, never the fixture secrets.

import json
import os

from google.genai import types

from harness import config, provider

JUDGE_MODEL = os.getenv("ENGRAM_JUDGE_MODEL", config.MODEL)

PROMPT = """You are grading one run of a coding agent. Be strict and literal.

## Task given to the agent
{prompt}

## Rubric (what a passing run must do)
{rubric}

## Tool calls the agent made (in order)
{trajectory}

## Files changed in the repo
{diff}

## Agent's final answer
{answer}

Score 1-5 against the rubric only (5 = fully meets it, 3 = partly, 1 = fails it).
Reply with JSON only: {{"score": <int>, "reason": "<one sentence>"}}"""


def _trajectory(run, limit=40):
    lines = []
    for e in run.tool_events[:limit]:
        status = "ok" if e.ok else "error"
        args = json.dumps(e.args, default=str)[:200]
        lines.append(f"- {e.name} {args} -> {status}: {e.text[:150]!r}")
    return "\n".join(lines) or "(none)"


def _diff(run, limit=4000):
    now = run.current_files()
    out = []
    for path in run.changed_files():
        after = now.get(path)
        out.append(f"### {path}\n" + (after.decode("utf-8", "replace")[:1500] if after else "(deleted)"))
    return "\n".join(out)[:limit] or "(no changes)"


class Judge:
    def __init__(self, threshold=4, model=JUDGE_MODEL):
        self.threshold = threshold
        self.model = model
        self._client = None

    def grade(self, run):
        if self._client is None:
            self._client = provider.get_client()
        prompt = PROMPT.format(
            prompt="\n---\n".join(run.task.prompts),
            rubric=run.task.rubric,
            trajectory=_trajectory(run),
            diff=_diff(run),
            answer=run.all_answers[:4000] or "(empty)",
        )
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json"),
        )
        data = json.loads(resp.text)
        score = int(data.get("score", 0))
        return score >= self.threshold, f"{score}/5: {data.get('reason', '')}"
