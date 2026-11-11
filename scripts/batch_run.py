"""Run the agent over a task split and save one trajectory per instance."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import yaml
from minisweagent.models.litellm_model import LitellmModel

from reporepair.harness import LoopAgent, StepRecord, TaskSpec, make_env, verify


def _short(command: str, limit: int = 90) -> str:
    first = (command or "").splitlines()
    return (first[0] if first else "")[:limit]


def run_one(instance_id: str, args, model) -> dict:
    task_dir = Path(args.tasks_dir) / instance_id
    out_path = Path(args.output) / f"{instance_id}.traj.json"
    if out_path.exists() and not args.force:
        data = json.loads(out_path.read_text(encoding="utf-8"))
        return {"id": instance_id, "skipped": True, "passed": (data.get("final") or {}).get("passed")}

    spec = TaskSpec.load(task_dir)
    env = make_env(spec, args.backend)
    started = time.time()
    try:
        if spec.setup_command:
            setup = env.execute({"command": spec.setup_command}, timeout=spec.timeout)
            if setup.get("returncode") != 0:
                return {
                    "id": instance_id,
                    "ok": False,
                    "stage": "setup",
                    "detail": (setup.get("output") or "")[-1000:],
                }

        agent = LoopAgent(
            model,
            env,
            task_id=spec.id,
            system_template=args.config["system_template"],
            instance_template=args.config["instance_template"],
            step_limit=args.steps,
            cost_limit=args.cost_limit,
            verifier=lambda: verify(env, spec.test_command, timeout=spec.timeout),
            verify_every=args.verify_every,
            on_step=lambda r: print(f"    [{r.step:>2}] $ {_short(r.actions[0].get('command', '')) if r.actions else ''}"),
        )
        trajectory = agent.run(spec.task)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        trajectory.save(out_path)
        final = trajectory.final
        return {
            "id": instance_id,
            "ok": final.passed if final else False,
            "exit_status": trajectory.exit_status,
            "calls": trajectory.n_calls,
            "cost": trajectory.cost,
            "duration_s": round(trajectory.duration_s, 1),
            "tests": f"{final.n_passed}p/{final.n_failed}f" if final else "",
            "elapsed_s": round(time.time() - started, 1),
        }
    finally:
        if cleanup := getattr(env, "cleanup", None):
            cleanup()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", required=True, help="task set JSONL, e.g. data/taskset/train.jsonl")
    parser.add_argument("--tasks-dir", default="tasks/swebench")
    parser.add_argument("--config", default="configs/harness.yaml")
    parser.add_argument("--backend", default="docker", choices=["local", "docker"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--cost-limit", type=float, default=1.0)
    parser.add_argument("--verify-every", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="re-run instances that already have a trajectory")
    parser.add_argument("--output", default="data/trajectories")
    parser.add_argument("--summary", default="data/trajectories/summary.json")
    args = parser.parse_args()
    args.config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))

    ids = [
        json.loads(line)["instance_id"]
        for line in Path(args.split).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.limit:
        ids = ids[: args.limit]

    model_name = args.model or "deepseek/deepseek-chat"
    model = LitellmModel(
        model_name=model_name,
        model_kwargs={"temperature": 0.0, "max_tokens": 4096, "drop_params": True},
    )

    results = []
    for i, instance_id in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] {instance_id}", flush=True)
        result = run_one(instance_id, args, model)
        print(f"    -> {result}", flush=True)
        results.append(result)

    ran = [r for r in results if not r.get("skipped")]
    solved = [r for r in ran if r.get("ok")]
    summary = {
        "model": model_name,
        "backend": args.backend,
        "total": len(results),
        "ran": len(ran),
        "solved": len(solved),
        "solve_rate": round(len(solved) / len(ran), 3) if ran else 0.0,
        "total_cost": round(sum(r.get("cost", 0.0) for r in ran), 4),
        "mean_cost": round(sum(r.get("cost", 0.0) for r in ran) / len(ran), 5) if ran else 0.0,
        "mean_calls": round(sum(r.get("calls", 0) for r in ran) / len(ran), 2) if ran else 0.0,
        "results": results,
    }
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
