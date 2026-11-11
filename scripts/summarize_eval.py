"""Compare base vs SFT eval manifests."""

import json
import pathlib
import statistics
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name: str) -> list[dict]:
    path = ROOT / "data/eval_results" / name / "manifest.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def summarize(name: str, rows: list[dict]) -> dict:
    if not rows:
        return {"model": name, "tasks": 0}
    passed = sum(1 for r in rows if r.get("passed"))
    steps = [r.get("steps", 0) for r in rows]
    dur = [r.get("duration_s", 0) for r in rows]
    return {
        "model": name,
        "tasks": len(rows),
        "passed": passed,
        "pass_rate": f"{passed / len(rows):.0%}",
        "avg_steps": round(statistics.mean(steps), 1),
        "median_steps": statistics.median(steps),
        "avg_duration_s": round(statistics.mean(dur), 1),
        "empty_patch": sum(1 for r in rows if r.get("patch_empty")),
        "exit_status": dict(Counter(r.get("exit_status") for r in rows)),
    }


base = summarize("base", load("base"))
sft = summarize("sft", load("sft"))

print(json.dumps({"base": base, "sft": sft}, indent=2, ensure_ascii=False))

# Per-task comparison when both sides have a result.
bmap = {r["instance_id"]: r for r in load("base")}
smap = {r["instance_id"]: r for r in load("sft")}
both = sorted(set(bmap) & set(smap))
if both:
    print("\ninstance_id                              base   sft   steps(base/sft)")
    for iid in both:
        b, s = bmap[iid], smap[iid]
        print(f"{iid:40s} {'PASS' if b.get('passed') else 'fail':4s}  "
              f"{'PASS' if s.get('passed') else 'fail':4s}  {b.get('steps',0)}/{s.get('steps',0)}")
