"""Build a small, leakage-safe task set from SWE-bench Lite.

Pipeline: filter -> de-duplicate -> repo-level split -> stratified sample -> materialise.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import yaml

from reporepair.tasks import select, swebench


def materialize(instance: dict, out_dir: Path) -> Path:
    task_dir = out_dir / instance["instance_id"]
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.md").write_text(instance["problem_statement"].strip() + "\n", encoding="utf-8")
    (task_dir / "gold.patch").write_text(instance["patch"], encoding="utf-8")
    (task_dir / "test.patch").write_text(instance["test_patch"], encoding="utf-8")

    setup_command, test_command = swebench.build_commands(instance)
    meta = {
        "id": instance["instance_id"],
        "task_file": "task.md",
        "repo": "",
        "test_command": test_command,
        "setup_command": setup_command,
        "image": swebench.image_name(instance["instance_id"]),
        "timeout": 900,
        "workdir": "/testbed",
        "mount_repo": False,
    }
    (task_dir / "task.yaml").write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return task_dir


def _summary(name: str, instances: list[dict]) -> dict:
    return {
        "name": name,
        "count": len(instances),
        "repos": dict(sorted(Counter(i["repo"] for i in instances).items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/swebench_lite/test.jsonl")
    parser.add_argument("--out", default="data/taskset")
    parser.add_argument("--tasks-dir", default="tasks/swebench")
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--eval-ratio", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    pool = swebench.load_jsonl(args.input)
    raw_count = len(pool)

    pool = select.filter_pool(pool, repos=swebench.PYTEST_REPOS)
    filtered_count = len(pool)

    unselectable = [i for i in pool if swebench.has_unselectable_ids(i)]
    pool = [i for i in pool if not swebench.has_unselectable_ids(i)]

    pool, dropped = select.dedup(pool)
    train_pool, eval_pool = select.split_by_repo(pool, eval_ratio=args.eval_ratio, seed=args.seed)

    n_eval = max(3, round(args.n * args.eval_ratio))
    eval_set = select.stratified_sample(eval_pool, n_eval, seed=args.seed)
    train_set = select.stratified_sample(train_pool, args.n - len(eval_set), seed=args.seed)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, instances in (("train", train_set), ("eval", eval_set)):
        with (out / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for inst in instances:
                f.write(json.dumps(inst, ensure_ascii=False) + "\n")

    for inst in train_set + eval_set:
        materialize(inst, Path(args.tasks_dir))

    stats = {
        "raw": raw_count,
        "after_filter": filtered_count,
        "unselectable_ids_dropped": len(unselectable),
        "duplicates_dropped": len(dropped),
        "after_dedup": len(pool),
        "train_pool": len(train_pool),
        "eval_pool": len(eval_pool),
        "splits": [_summary("train", train_set), _summary("eval", eval_set)],
    }
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
