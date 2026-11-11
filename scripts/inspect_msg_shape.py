"""Inspect raw trajectory message shapes."""

import json
import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
p = next((root / "data/trajectories").glob("*/rollout_0.traj.json"))
traj = json.loads(p.read_text(encoding="utf-8"))
print("file:", p)
print("keys:", list(traj))
for i, m in enumerate(traj["messages"][:8]):
    print("=" * 50)
    print("index", i, "role", m.get("role"))
    print("keys:", list(m))
    print("content:", repr(m.get("content"))[:200])
    if "tool_calls" in m:
        print("tool_calls:", json.dumps(m["tool_calls"])[:400])
    if "extra" in m:
        print("extra keys:", list(m["extra"]))
