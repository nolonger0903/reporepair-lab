"""Inspect the SFT dataset for repetition and edit actions."""

import json
import pathlib
from collections import Counter

root = pathlib.Path(__file__).resolve().parents[1]
recs = [json.loads(l) for l in (root / "data/clean/sft.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

EDIT_HINTS = ("sed -i", ">>", "cat >", "tee ", "python - <<", "patch ", "apply_patch", "git apply", "perl -i", "vim", "nano")
total_cmds = 0
repeat_records = 0
edit_records = 0
edit_ratio = []
for r in recs:
    cmds = []
    for m in r["messages"]:
        for tc in (m.get("tool_calls") or []):
            try:
                cmds.append(json.loads(tc["function"]["arguments"]).get("command", ""))
            except Exception:
                pass
    total_cmds += len(cmds)
    dup = len(cmds) - len(set(cmds))
    if cmds and dup / len(cmds) > 0.2:
        repeat_records += 1
    edits = [c for c in cmds if any(h in c for h in EDIT_HINTS)]
    if edits:
        edit_records += 1
    edit_ratio.append(len(edits) / max(len(cmds), 1))

print("records:", len(recs))
print("commands:", total_cmds, "avg/record:", round(total_cmds / len(recs), 1))
print("records with >20% duplicate commands:", repeat_records)
print("records containing an edit command:", edit_records)
print("avg edit-command ratio:", round(sum(edit_ratio) / len(edit_ratio), 3))
