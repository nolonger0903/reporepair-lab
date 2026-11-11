"""Build the full training split, excluding every repository used for evaluation.

Unlike ``build_taskset.py`` this keeps the *entire* usable training pool rather than
sampling: trajectory collection is expensive, so we want every task available.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from reporepair.tasks import select, swebench
from reporepair.tasks.materialize import materialize

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "data/raw/swebench_lite/test.jsonl"))
    parser.add_argument("--eval-split", default=str(ROOT / "data/taskset/eval_verified.jsonl"))
    parser.add_argument("--out", default=str(ROOT / "data/taskset/train_full.jsonl"))
    parser.add_argument("--tasks-dir", default=str(ROOT / "tasks/swebench"))
    args = parser.parse_args()

    eval_rows = [
        json.loads(line) for line in Path(args.eval_split).read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    eval_repos = {row["repo"] for row in eval_rows}
    eval_ids = {row["instance_id"] for row in eval_rows}

    pool = swebench.load_jsonl(args.input)
    raw_count = len(pool)
    pool = select.filter_pool(pool, repos=swebench.PYTEST_REPOS)
    after_filter = len(pool)

    unselectable = [row for row in pool if swebench.has_unselectable_ids(row)]
    pool = [row for row in pool if not swebench.has_unselectable_ids(row)]

    pool = [row for row in pool if row["repo"] not in eval_repos and row["instance_id"] not in eval_ids]
    pool, dropped = select.dedup(pool)
    pool.sort(key=lambda row: (row["repo"], row["instance_id"]))

    for row in pool:
        materialize(row, Path(args.tasks_dir))

    with Path(args.out).open("w", encoding="utf-8") as f:
        for row in pool:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "raw": raw_count,
                "after_filter": after_filter,
                "unselectable_dropped": len(unselectable),
                "eval_repos_excluded": sorted(eval_repos),
                "duplicates_dropped": len(dropped),
                "train_instances": len(pool),
                "by_repo": dict(sorted(Counter(row["repo"] for row in pool).items())),
                "output": args.out,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
