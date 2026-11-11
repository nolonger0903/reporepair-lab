"""Diagnostic: compare expected node ids against what the container actually collects."""

import sys

from reporepair.harness.environment import make_env
from reporepair.harness.protocol import TaskSpec
from reporepair.tasks.swebench import as_list, load_jsonl

instance_id = sys.argv[1]
spec = TaskSpec.load(f"tasks/swebench/{instance_id}")
row = next(r for r in load_jsonl("data/raw/swebench_lite/test.jsonl") if r["instance_id"] == instance_id)

env = make_env(spec, "docker")
try:
    print(env.execute({"command": spec.setup_command})["returncode"], "setup")
    out = env.execute(
        {"command": "python -m pytest --collect-only -q testing/test_assertion.py 2>&1 | grep iterable_full_diff"},
        timeout=300,
    )["output"]
    print("--- collected ---")
    print(out[:1200])
    print("--- expected ---")
    for t in as_list(row["PASS_TO_PASS"]):
        if "iterable_full_diff" in t:
            print(repr(t))
finally:
    env.cleanup()
