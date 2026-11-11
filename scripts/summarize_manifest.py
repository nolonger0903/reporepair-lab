"""Summarize a collection manifest."""

import collections
import json
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/trajectories/manifest.jsonl")
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

print(f"rollouts: {len(rows)}")
by_instance = collections.defaultdict(list)
for row in rows:
    by_instance[row["instance_id"]].append(row)

total_cost = sum(r["cost"] for r in rows)
total_calls = sum(r["calls"] for r in rows)
total_secs = sum(r["duration_s"] for r in rows)
print(f"total cost: ${total_cost:.4f} | calls: {total_calls} | agent seconds: {total_secs:.0f}")
print()
for instance_id, records in sorted(by_instance.items()):
    solved = sum(1 for r in records if r["passed"])
    print(f"{instance_id:<28} {solved}/{len(records)} solved | "
          f"steps={[r['steps'] for r in records]} calls={[r['calls'] for r in records]} "
          f"cost={[round(r['cost'],4) for r in records]} empty_patch={[r['patch_empty'] for r in records]}")

solved = sum(1 for r in rows if r["passed"])
print(f"\noverall rollout success: {solved}/{len(rows)} = {solved/len(rows):.0%}")
inst_solved = sum(1 for recs in by_instance.values() if any(r["passed"] for r in recs))
print(f"instances solved at least once: {inst_solved}/{len(by_instance)}")
