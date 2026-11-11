"""Diagnostic: reproduce the resolve() failure on a task directory."""

from pathlib import Path

targets = [
    "tasks/swebench/pytest-dev__pytest-5692",
    "tasks/swebench/pytest-dev__pytest-8906",
    "tasks/swebench/pytest-dev__pytest-9359",
]
for target in targets:
    path = Path(target)
    print("exists:", path.exists(), "|", target)
    try:
        print("  resolved:", path.resolve())
    except Exception as e:
        print("  resolve FAILED:", type(e).__name__, e)
