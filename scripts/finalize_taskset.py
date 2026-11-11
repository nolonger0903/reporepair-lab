"""Turn a verification report into verified / rejected task splits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default=str(ROOT / "data/taskset/eval.jsonl"))
    parser.add_argument("--report", default=str(ROOT / "data/taskset/verify_report.json"))
    parser.add_argument("--out-dir", default=str(ROOT / "data/taskset"))
    args = parser.parse_args()

    rows = [json.loads(line) for line in Path(args.split).read_text(encoding="utf-8").splitlines() if line.strip()]
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    ok_ids = {r["id"] for r in report["results"] if r["ok"]}
    stage_by_id = {r["id"]: r["stage"] for r in report["results"]}

    verified = [row for row in rows if row["instance_id"] in ok_ids]
    rejected = [row["instance_id"] for row in rows if row["instance_id"] not in ok_ids]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "eval_verified.jsonl").open("w", encoding="utf-8") as f:
        for row in verified:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_dir / "rejected.json").write_text(
        json.dumps(
            {"rejected": [{"id": i, "stage": stage_by_id.get(i, "unverified")} for i in rejected]},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"verified": len(verified), "rejected": rejected}, indent=2))


if __name__ == "__main__":
    main()
