"""Sanity-check the task set: duplicate similarity distribution and artifact shape."""

import itertools
import json
from pathlib import Path

from reporepair.tasks import select, swebench


def main() -> None:
    pool = swebench.load_jsonl("data/raw/swebench_lite/test.jsonl")
    pool = select.filter_pool(pool, repos=swebench.PYTEST_REPOS)

    pairs = []
    for a, b in itertools.combinations(pool, 2):
        if a["repo"] != b["repo"]:
            continue
        pairs.append((select.jaccard(select.tokens(a["problem_statement"]), select.tokens(b["problem_statement"])), a["instance_id"], b["instance_id"]))
    pairs.sort(reverse=True)
    print(f"same-repo pairs: {len(pairs)}")
    print("top-5 jaccard:")
    for score, x, y in pairs[:5]:
        print(f"  {score:.3f}  {x}  {y}")
    for threshold in (0.6, 0.7, 0.8, 0.85, 0.9):
        print(f"  pairs above {threshold}: {sum(1 for s, _, _ in pairs if s > threshold)}")

    eval_set = swebench.load_jsonl("data/taskset/eval.jsonl")
    print("\neval instance:", eval_set[0]["instance_id"])
    task_dir = Path("tasks/swebench") / eval_set[0]["instance_id"]
    print("files:", sorted(p.name for p in task_dir.iterdir()))
    meta = json.loads("{}") if False else None
    print("--- task.yaml ---")
    print((task_dir / "task.yaml").read_text()[:600])
    print("--- gold.patch head ---")
    print((task_dir / "gold.patch").read_text()[:300])


if __name__ == "__main__":
    main()
