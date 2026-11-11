"""Diagnostic: how many selected instances have test ids that cannot be selected directly."""

import json
from pathlib import Path

from reporepair.tasks.swebench import as_list


def weird(ids: list[str]) -> dict[str, int]:
    return {
        "backslash_n": sum(1 for t in ids if "\\n" in t),
        "real_newline": sum(1 for t in ids if "\n" in t),
        "single_quote": sum(1 for t in ids if "'" in t),
        "double_quote": sum(1 for t in ids if '"' in t),
        "total": len(ids),
    }


def main() -> None:
    for split in ("train", "eval"):
        rows = [json.loads(line) for line in Path(f"data/taskset/{split}.jsonl").read_text(encoding="utf-8").splitlines()]
        affected = 0
        print(f"=== {split} ({len(rows)} instances) ===")
        for row in rows:
            ids = as_list(row["FAIL_TO_PASS"]) + as_list(row["PASS_TO_PASS"])
            counts = weird(ids)
            if counts["backslash_n"] or counts["real_newline"]:
                affected += 1
                print(f"  {row['instance_id']}: {counts}")
        print(f"  affected instances: {affected}/{len(rows)}")


if __name__ == "__main__":
    main()
