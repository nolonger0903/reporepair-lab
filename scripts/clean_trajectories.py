"""Filter raw trajectories and export SFT-ready JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reporepair.data import filter as traj_filter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", help="trajectory JSON files")
    parser.add_argument("--out", default="data/clean/sft.jsonl")
    parser.add_argument("--allow-fail", action="store_true", help="keep trajectories whose tests did not pass")
    parser.add_argument("--max-cost", type=float, default=None)
    parser.add_argument("--max-steps", type=int, default=None)
    args = parser.parse_args()

    raw = traj_filter.load_many(args.paths)
    kept, reasons = traj_filter.filter_trajectories(
        raw,
        require_pass=not args.allow_fail,
        max_cost=args.max_cost,
        max_steps=args.max_steps,
    )
    deduped, n_dups = traj_filter.dedup_trajectories(kept)
    n_written = traj_filter.export_sft(deduped, args.out)

    print(
        json.dumps(
            {
                "input": len(raw),
                "kept": len(kept),
                "dropped": reasons,
                "duplicates": n_dups,
                "exported": n_written,
                "output": args.out,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
