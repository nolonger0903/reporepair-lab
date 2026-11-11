"""Diagnostic: show which tests still fail after the gold patch is applied."""

import sys

from reporepair.harness.environment import make_env
from reporepair.harness.protocol import TaskSpec

instance_id = sys.argv[1]
spec = TaskSpec.load(f"tasks/swebench/{instance_id}")

env = make_env(spec, "docker")
try:
    print(env.execute({"command": spec.setup_command})["returncode"], "setup")
    if len(sys.argv) > 2 and sys.argv[2] == "gold":
        print(env.execute({"command": "git apply -v /rrl/gold.patch"})["returncode"], "gold")
    result = env.execute({"command": spec.test_command}, timeout=900)
    output = result["output"] or ""
    lines = output.splitlines()
    failed = [line for line in lines if line.startswith(("FAILED ", "ERROR "))]
    print("returncode:", result["returncode"], "| total lines:", len(lines), "| failed lines:", len(failed))
    for line in failed[:30]:
        print("  ", line[:160])
    print("--- tail ---")
    print(output[-1200:])
finally:
    env.cleanup()
