"""Create a subset split for a pilot run (by instance id or repository)."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data/taskset/train_full.jsonl")
    parser.add_argument("--pick", help="single instance_id")
    parser.add_argument("--repo", help="take every instance of this repository")
    parser.add_argument("--out", default="data/taskset/smoke.jsonl")
    args = parser.parse_args()

    rows = [json.loads(line) for line in Path(args.source).read_text(encoding="utf-8").splitlines() if line.strip()]

    if args.pick:
        chosen = [row for row in rows if row["instance_id"] == args.pick]
    elif args.repo:
        chosen = [row for row in rows if row["repo"] == args.repo]
    else:
        raise SystemExit("pass --pick or --repo")

    if not chosen:
        raise SystemExit(f"nothing matched; available repos: {sorted({r['repo'] for r in rows})}")

    Path(args.out).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in chosen) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.out}: {len(chosen)} instances")
    for row in chosen:
        print("  ", row["instance_id"])


if __name__ == "__main__":
    main()
