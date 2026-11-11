"""Diagnostic: inspect how test node ids are stored for one instance."""

import sys

from reporepair.tasks.swebench import as_list, load_jsonl

instance_id = sys.argv[1] if len(sys.argv) > 1 else "pytest-dev__pytest-5495"
needle = sys.argv[2] if len(sys.argv) > 2 else "iterable_full_diff"

row = next(r for r in load_jsonl("data/raw/swebench_lite/test.jsonl") if r["instance_id"] == instance_id)
for field in ("FAIL_TO_PASS", "PASS_TO_PASS"):
    ids = as_list(row[field])
    hits = [t for t in ids if needle in t]
    print(f"{field}: {len(ids)} ids, {len(hits)} matching {needle!r}")
    for t in hits[:3]:
        print("   repr:", repr(t))
