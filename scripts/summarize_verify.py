"""Summarize a task-set verification report."""

import json
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/taskset/verify_report.json")
report = json.loads(path.read_text(encoding="utf-8"))

print(f"total={report['total']} ok={report['ok']} failed={len(report['failed'])}")
for result in report["results"]:
    print(f"  {result['id']:<45} ok={result['ok']!s:<5} stage={result['stage']}")

for result in report["failed"]:
    print(f"\n=== FAILED {result['id']} (stage={result['stage']}) ===")
    if "baseline" in result:
        print("baseline:  ", result["baseline"])
        print("after_gold:", result.get("after_gold"))
    detail = result.get("detail", "")
    print(detail[-1200:])
