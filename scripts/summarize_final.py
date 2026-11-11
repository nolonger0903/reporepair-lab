"""Summarize the collected training trajectories."""

import json
import pathlib
from collections import Counter, defaultdict

root = pathlib.Path(__file__).resolve().parents[1]
rows = [json.loads(l) for l in (root / "data/taskset/train_full.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

full, partial, missing = [], [], []
for r in rows:
    d = root / "data/trajectories" / r["instance_id"]
    n = len(list(d.glob("rollout_*.traj.json"))) if d.exists() else 0
    (full if n >= 3 else partial if n > 0 else missing).append((r, n))

print("任务: 完整3条", len(full), "| 部分", len(partial), "| 无轨迹", len(missing))

man = [json.loads(l) for l in (root / "data/trajectories/manifest.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
p = sum(1 for r in man if r["passed"])
cost = sum(r["cost"] for r in man)
print("manifest 总记录:", len(man))
print(f"通过: {p}/{len(man)} = {p/len(man):.0%}  成本: ${cost:.2f}")

by = defaultdict(lambda: [0, 0])
for r in man:
    repo = r["instance_id"].split("__")[0]
    by[repo][1] += 1
    by[repo][0] += r["passed"]
for repo, (a, b) in sorted(by.items()):
    print(f"  {repo:12s} {a}/{b}")

print("无轨迹任务:", [x[0]["instance_id"] for x in missing])
print("部分任务:", [(x[0]["instance_id"], x[1]) for x in partial])

rej = [json.loads(l) for l in (root / "data/trajectories/rejected.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
print("本轮 rejected:", len(rej), dict(Counter(r["stage"] for r in rej)))
print("rejected ids:", [r["instance_id"] for r in rej])
