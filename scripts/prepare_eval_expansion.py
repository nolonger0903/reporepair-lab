"""Materialize extra scikit-learn eval candidates and write their split."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_taskset import materialize  # noqa: E402
from reporepair.tasks import swebench  # noqa: E402

ALREADY_VERIFIED = {
    "scikit-learn__scikit-learn-10508",
    "scikit-learn__scikit-learn-13439",
    "scikit-learn__scikit-learn-13779",
    "scikit-learn__scikit-learn-14894",
    "scikit-learn__scikit-learn-14983",
}

pool = swebench.load_jsonl(ROOT / "data/raw/swebench_lite/test.jsonl")
candidates = [
    i
    for i in pool
    if i["repo"] == "scikit-learn/scikit-learn"
    and not swebench.has_unselectable_ids(i)
    and i["instance_id"] not in ALREADY_VERIFIED
]

split = ROOT / "data/taskset/eval_candidates.jsonl"
with split.open("w", encoding="utf-8") as f:
    for inst in candidates:
        f.write(json.dumps(inst, ensure_ascii=False) + "\n")

for inst in candidates:
    materialize(inst, ROOT / "tasks/swebench")

print(f"candidates: {len(candidates)}")
for inst in candidates:
    print(" ", inst["instance_id"])
