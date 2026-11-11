"""Evaluate a model on the held-out eval set with the same agent harness.

Unlike collect.py this does not re-validate gold (the eval set is already verified)
and it intentionally runs on evaluation repositories. Images are still pulled and
removed one repository at a time to respect the local disk budget.

The model can be any OpenAI-compatible endpoint, e.g. a vLLM server on the GPU box:

    OPENAI_API_BASE=http://127.0.0.1:8000/v1 OPENAI_API_KEY=dummy \
    python scripts/evaluate.py --split data/taskset/eval_verified.jsonl \
        --model openai/Qwen2.5-Coder-7B-Instruct --out data/eval_results/base

    ... --model openai/sft --out data/eval_results/sft
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml
from minisweagent.models.litellm_model import LitellmModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect import (  # noqa: E402
    disk_free_gb,
    image_present,
    pull_image,
    remove_image,
    run_agent,
    score_patch,
)
from reporepair.harness import TaskSpec  # noqa: E402
from reporepair.tasks.swebench import image_name  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", required=True)
    parser.add_argument("--tasks-dir", default=str(ROOT / "tasks/swebench"))
    parser.add_argument("--config", default=str(ROOT / "configs/harness.yaml"))
    parser.add_argument("--model", required=True, help="litellm model name, e.g. openai/sft")
    parser.add_argument("--rollouts", type=int, default=1)
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument("--cost-limit", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=300, help="per-command timeout inside the container")
    parser.add_argument("--min-free-gb", type=float, default=40.0)
    parser.add_argument("--keep-images", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    split_path = Path(args.split).resolve()
    rows = [json.loads(line) for line in split_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        rows = rows[: args.limit]

    by_repo: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_repo[row["repo"]].append(row)

    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    manifest = out_root / "manifest.jsonl"

    model = LitellmModel(
        model_name=args.model,
        model_kwargs={"temperature": 0.0, "max_tokens": 1024, "drop_params": True},
    )

    tasks_dir = Path(args.tasks_dir).resolve()
    os.chdir("/")

    for repo, instances in sorted(by_repo.items()):
        free = disk_free_gb()
        print(f"\n=== {repo} ({len(instances)} instances) | disk free {free:.1f} GiB ===", flush=True)
        if free < args.min_free_gb:
            sys.exit(f"aborting: free disk {free:.1f} GiB < {args.min_free_gb} GiB")

        images = [(row["instance_id"], image_name(row["instance_id"])) for row in instances]
        for instance_id, image in images:
            t0 = time.time()
            ok, message = pull_image(image, timeout=900)
            print(f"  pull {instance_id}: {message} ({time.time() - t0:.0f}s)", flush=True)
            if not ok:
                with manifest.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"instance_id": instance_id, "stage": "pull", "detail": message}) + "\n")

        for instance_id, image in images:
            if not image_present(image):
                continue
            spec = TaskSpec.load(tasks_dir / instance_id)
            # Cap long commands: a model that runs the whole suite would otherwise
            # block for the task's 900 s timeout on every step.
            spec.timeout = args.timeout
            for k in range(args.rollouts):
                started = time.time()
                trajectory, patch = run_agent(spec, model, config, args)
                result = score_patch(spec, patch, spec.timeout)
                record = {
                    "instance_id": instance_id,
                    "rollout": k,
                    "model": args.model,
                    "passed": result.passed,
                    "reward": result.reward,
                    "n_passed": result.n_passed,
                    "n_failed": result.n_failed,
                    "patch_empty": not patch.strip(),
                    "exit_status": trajectory.exit_status,
                    "calls": trajectory.n_calls,
                    "steps": len(trajectory.steps),
                    "duration_s": round(time.time() - started, 1),
                    "patch": patch,
                }
                with manifest.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                print(
                    f"  {instance_id}: passed={result.passed} reward={result.reward} "
                    f"steps={len(trajectory.steps)} calls={trajectory.n_calls} "
                    f"({time.time() - started:.0f}s)",
                    flush=True,
                )

        if not args.keep_images:
            leftover = [image for _, image in images if not remove_image(image)]
            print(f"  removed images: {'all' if not leftover else leftover}", flush=True)


if __name__ == "__main__":
    main()
