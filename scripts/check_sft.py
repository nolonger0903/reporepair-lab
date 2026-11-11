"""Sanity-check the exported SFT file."""

import json
import pathlib
from collections import Counter

path = pathlib.Path(__file__).resolve().parents[1] / "data/clean/sft.jsonl"
records = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

print("records:", len(records))
roles = Counter()
n_msgs = []
bad = Counter()
for r in records:
    n_msgs.append(len(r["messages"]))
    for m in r["messages"]:
        roles[m["role"]] += 1
        if m["role"] == "exit":
            bad["exit_message"] += 1
        if "gold.patch" in m["content"] or "/rrl" in m["content"]:
            bad["leak"] += 1
        if not m["content"] and not m.get("tool_calls"):
            bad["empty_without_tool_calls"] += 1
        if m["role"] == "tool" and not m.get("tool_call_id"):
            bad["tool_without_call_id"] += 1

print("roles:", dict(roles))
print("messages per record: min", min(n_msgs), "max", max(n_msgs), "avg", round(sum(n_msgs) / len(n_msgs), 1))
print("problems:", dict(bad) or "none")
print("task ids:", len({r["task_id"] for r in records}), "unique")
print("\n--- first record ---")
r = records[0]
print("task_id:", r["task_id"], "reward:", r["reward"])
for m in r["messages"][:4]:
    print(f"[{m['role']}] {m['content'][:160]!r}")
print("...")
print(f"[{r['messages'][-1]['role']}] {r['messages'][-1]['content'][:200]!r}")
