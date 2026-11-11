"""Pull the SWE-bench Docker images for a task split."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from reporepair.tasks.swebench import image_name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="data/taskset/eval.jsonl")
    parser.add_argument("--only-missing", action="store_true")
    args = parser.parse_args()

    ids = [
        json.loads(line)["instance_id"]
        for line in Path(args.split).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    existing = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}"], capture_output=True, text=True
    ).stdout.split()

    failures = []
    for i, instance_id in enumerate(ids, 1):
        image = image_name(instance_id)
        repo = image.split(":")[0]
        if args.only_missing and repo in existing:
            print(f"[{i}/{len(ids)}] {instance_id}: already present", flush=True)
            continue
        print(f"[{i}/{len(ids)}] {instance_id}: pulling", flush=True)
        result = subprocess.run(["docker", "pull", "-q", image], capture_output=True, text=True)
        status = "ok" if result.returncode == 0 else "FAILED"
        print(f"    -> {status} {result.stderr.strip()[:200]}", flush=True)
        if result.returncode != 0:
            failures.append(instance_id)

    print(json.dumps({"total": len(ids), "failures": failures}, indent=2))


if __name__ == "__main__":
    main()
