"""Create a one-instance split for a smoke test."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data/taskset/train.jsonl")
    parser.add_argument("--pick", required=True, help="instance_id to keep")
    parser.add_argument("--out", default="data/taskset/smoke.jsonl")
    args = parser.parse_args()

    rows = [json.loads(line) for line in Path(args.source).read_text(encoding="utf-8").splitlines() if line.strip()]
    chosen = [row for row in rows if row["instance_id"] == args.pick]
    if not chosen:
        raise SystemExit(f"{args.pick} not found in {args.source}; available: {[r['instance_id'] for r in rows]}")
    Path(args.out).write_text(json.dumps(chosen[0], ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out} with {args.pick} ({chosen[0]['repo']})")


if __name__ == "__main__":
    main()
