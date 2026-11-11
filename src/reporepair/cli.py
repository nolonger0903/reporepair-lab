"""Command line interface: ``rrl-run run`` and ``rrl-run replay``."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml
from minisweagent.models.litellm_model import LitellmModel

from .harness import LoopAgent, StepRecord, TaskSpec, make_env, verify
from .harness import trajectory as traj_utils


def _load_agent_config(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _print_step(record: StepRecord) -> None:
    for action in record.actions:
        command = (action.get("command") or "").splitlines()
        head = command[0] if command else ""
        print(f"  [{record.step:>2}] $ {head[:100]}")
    if record.verify:
        status = "PASS" if record.verify.passed else "FAIL"
        print(f"       verify: {status} ({record.verify.n_passed} passed, {record.verify.n_failed} failed)")


def run(args: argparse.Namespace) -> int:
    spec = TaskSpec.load(args.task)
    env = make_env(spec, args.backend)
    if spec.setup_command:
        env.execute({"command": spec.setup_command})

    config = _load_agent_config(args.config)
    model_name = args.model or os.getenv("MSWEA_MODEL_NAME", "deepseek/deepseek-chat")
    model = LitellmModel(
        model_name=model_name,
        model_kwargs={"temperature": 0.0, "max_tokens": 4096, "drop_params": True},
    )

    agent = LoopAgent(
        model,
        env,
        task_id=spec.id,
        system_template=config["system_template"],
        instance_template=config["instance_template"],
        step_limit=args.steps,
        cost_limit=args.cost_limit,
        verifier=lambda: verify(env, spec.test_command, timeout=spec.timeout),
        verify_every=args.verify_every,
        on_step=_print_step,
    )
    print(f"task={spec.id} backend={args.backend} model={model_name}")
    trajectory = agent.run(spec.task)
    trajectory.save(args.output)

    final = trajectory.final
    print(
        json.dumps(
            {
                "exit_status": trajectory.exit_status,
                "submission": trajectory.submission.strip(),
                "calls": trajectory.n_calls,
                "cost_usd": round(trajectory.cost, 6),
                "duration_s": round(trajectory.duration_s, 1),
                "passed": final.passed if final else None,
                "tests": f"{final.n_passed} passed / {final.n_failed} failed" if final else None,
                "reward": final.reward if final else None,
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if (final and final.passed) else 1


def replay(args: argparse.Namespace) -> int:
    spec = TaskSpec.load(args.task)
    trajectory = traj_utils.load(args.trajectory)
    env = make_env(spec, args.backend)

    def reset() -> None:
        subprocess.run(["git", "-C", str(spec.repo), "checkout", "--", "."], check=False)
        subprocess.run(["git", "-C", str(spec.repo), "clean", "-fdq"], check=False)

    results = traj_utils.replay(trajectory, env, reset=reset)
    diffs = traj_utils.compare_replay(trajectory, results)
    print(json.dumps({"actions_replayed": len(results), "returncode_diffs": diffs}, ensure_ascii=False, indent=2))
    return 0 if not diffs else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rrl-run", description="RepoRepair-Lab harness CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run the agent on a task")
    p_run.add_argument("--task", required=True, help="task directory containing task.yaml")
    p_run.add_argument("--config", default="configs/harness.yaml", help="agent prompt config")
    p_run.add_argument("--model", default=None, help="litellm model name (default: $MSWEA_MODEL_NAME)")
    p_run.add_argument("--backend", default="local", choices=["local", "docker"])
    p_run.add_argument("--steps", type=int, default=30)
    p_run.add_argument("--cost-limit", type=float, default=1.0)
    p_run.add_argument("--verify-every", type=int, default=0, help="run verification every N steps (0 = only at the end)")
    p_run.add_argument("--output", type=Path, required=True)
    p_run.set_defaults(func=run)

    p_replay = sub.add_parser("replay", help="replay a recorded trajectory")
    p_replay.add_argument("--task", required=True)
    p_replay.add_argument("--trajectory", required=True)
    p_replay.add_argument("--backend", default="local", choices=["local", "docker"])
    p_replay.set_defaults(func=replay)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
