"""Independent validation of a task set.

For every task we require:
  1. the baseline (test patch applied, no fix)      -> tests FAIL
  2. the gold patch applied                         -> tests PASS
Any task that does not show this transition is unusable for training or evaluation.

Requires Docker and the SWE-bench instance images.
"""

from __future__ import annotations

import argparse
import json
import os
import traceback
from pathlib import Path

from reporepair.harness.environment import make_env
from reporepair.harness.protocol import TaskSpec
from reporepair.harness.reward import verify

ROOT = Path(__file__).resolve().parents[1]


def check_task(task_dir: Path, *, timeout: int) -> dict:
    env = None
    try:
        spec = TaskSpec.load(task_dir)
        env = make_env(spec, "docker")

        setup = env.execute({"command": spec.setup_command}, timeout=timeout)
        if setup.get("returncode") != 0:
            return {"id": spec.id, "ok": False, "stage": "setup", "detail": (setup.get("output") or "")[-1500:]}

        before = verify(env, spec.test_command, timeout=timeout)
        if before.passed:
            return {"id": spec.id, "ok": False, "stage": "baseline_should_fail", "detail": before.output[-1500:]}

        patch = env.execute({"command": "git apply -v /rrl/gold.patch"}, timeout=timeout)
        if patch.get("returncode") != 0:
            return {"id": spec.id, "ok": False, "stage": "apply_gold", "detail": (patch.get("output") or "")[-1500:]}

        after = verify(env, spec.test_command, timeout=timeout)
        return {
            "id": spec.id,
            "ok": after.passed,
            "stage": "done" if after.passed else "gold_should_pass",
            "baseline": {"passed": before.passed, "n_passed": before.n_passed, "n_failed": before.n_failed},
            "after_gold": {"passed": after.passed, "n_passed": after.n_passed, "n_failed": after.n_failed},
            "detail": "" if after.passed else after.output[-1500:],
        }
    except Exception as e:  # container failures must not abort the whole sweep
        return {
            "id": task_dir.name,
            "ok": False,
            "stage": "exception",
            "detail": f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}",
        }
    finally:
        if env is not None and (cleanup := getattr(env, "cleanup", None)):
            cleanup()


def _write_report(path: Path, results: list[dict]) -> dict:
    report = {
        "total": len(results),
        "ok": sum(1 for r in results if r["ok"]),
        "failed": [r for r in results if not r["ok"]],
        "results": results,
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-dir", default=str(ROOT / "tasks/swebench"))
    parser.add_argument("--split", default=str(ROOT / "data/taskset/eval.jsonl"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--out", default=str(ROOT / "data/taskset/verify_report.json"))
    args = parser.parse_args()

    # Docker container churn can transiently invalidate a cwd on /mnt/c, and
    # pathlib.resolve() calls os.getcwd() internally. Anchor to "/" and use
    # absolute paths so the sweep cannot die on a hostile getcwd().
    os.chdir("/")

    split_path = Path(args.split).resolve()
    ids = [
        json.loads(line)["instance_id"]
        for line in split_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.limit:
        ids = ids[: args.limit]

    tasks_dir = Path(args.tasks_dir).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for i, instance_id in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] {instance_id} ...", flush=True)
        result = check_task(tasks_dir / instance_id, timeout=args.timeout)
        print(f"    -> ok={result['ok']} stage={result['stage']}", flush=True)
        results.append(result)
        # Persist after every task so a crash late in the sweep loses nothing.
        _write_report(out_path, results)

    report = _write_report(out_path, results)
    print(json.dumps({"total": report["total"], "ok": report["ok"], "failed": len(report["failed"])}, indent=2))


if __name__ == "__main__":
    main()
