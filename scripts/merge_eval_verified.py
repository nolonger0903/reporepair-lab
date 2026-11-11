"""Merge verified eval candidates into eval_verified.jsonl, capped at 20 tasks."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = 20

verified_path = ROOT / "data/taskset/eval_verified.jsonl"
candidates_path = ROOT / "data/taskset/eval_candidates.jsonl"
report_path = ROOT / "data/taskset/verify_report_candidates.json"

verified = [json.loads(l) for l in verified_path.read_text(encoding="utf-8").splitlines() if l.strip()]
candidates = [json.loads(l) for l in candidates_path.read_text(encoding="utf-8").splitlines() if l.strip()]
report = json.loads(report_path.read_text(encoding="utf-8"))
ok_ids = {r["id"] for r in report["results"] if r["ok"]}

seen = {r["instance_id"] for r in verified}
added = []
for row in candidates:
    if len(verified) + len(added) >= TARGET:
        break
    if row["instance_id"] in ok_ids and row["instance_id"] not in seen:
        added.append(row)
        seen.add(row["instance_id"])

merged = verified + added
with verified_path.open("w", encoding="utf-8") as f:
    for row in merged:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

# Keep the default verification split in sync with what we actually verified.
with (ROOT / "data/taskset/eval.jsonl").open("w", encoding="utf-8") as f:
    for row in merged:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

from collections import Counter

print(json.dumps({
    "before": len(verified),
    "added": [r["instance_id"] for r in added],
    "total": len(merged),
    "repos": dict(Counter(r["repo"] for r in merged)),
    "unused_verified_candidates": sorted(ok_ids - {r["instance_id"] for r in merged}),
}, indent=2))
