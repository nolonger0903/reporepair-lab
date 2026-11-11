"""Collect SWE-bench trajectories with strict test isolation.

Two containers per rollout:

    agent     pristine image, no task directory mount, no test patch
              -> the agent can never see gold.patch or the expected tests
    verifier  agent patch + official test patch, then run the tests

Images are pulled one repository at a time (they share layers), used, then deleted, so
peak disk stays at roughly one repository instead of the whole task set.

Safety rules for a shared server:
  * only ``docker rmi <exact image we pulled>``; never a global prune
  * containers are started with --rm by the environment and stopped in ``finally``
  * the run aborts if free disk drops below --min-free-gb
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml
from minisweagent.models.litellm_model import LitellmModel

from reporepair.harness import LoopAgent, TaskSpec, make_env, verify
from reporepair.harness.protocol import VerifyResult
from reporepair.tasks.swebench import image_name

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- docker helpers


def _docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def disk_free_gb() -> float:
    """Free space on the host disk that actually stores Docker images.

    Inside WSL ``/`` is a virtual 1 TB disk, so ``disk_usage("/")`` reports ~945 GB
    free no matter how full the Windows drive is. The Docker data vhdx lives on
    ``/mnt/c``, so that is what we must watch. Units are GiB to match Explorer.
    """
    target = "/mnt/c" if Path("/mnt/c").exists() else "/"
    return shutil.disk_usage(target).free / 1024**3


def image_present(image: str) -> bool:
    # When Docker Desktop is stopped, the WSL docker shim prints its error to *stdout*
    # and exits non-zero. Checking stdout alone would then report every image as present.
    result = _docker("images", "-q", image)
    return result.returncode == 0 and bool(result.stdout.strip())


# Docker Hub is often unreachable from mainland servers; the mirrors below are tried in
# order for every layer. Pulling through a mirror tags the image differently, so we
# re-tag it to the canonical name the task files expect.
PULL_MIRRORS = ["", "docker.m.daocloud.io", "docker.1ms.run"]


def _pull_once(target: str, timeout: int) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["docker", "pull", "-q", target],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        # A stalled pull never raises on its own; without this the run hangs forever.
        return False, f"stalled (no completion in {timeout}s)"
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()[:200]
    return True, "pulled"


def pull_image(image: str, *, timeout: int = 900, retries: int = 2) -> tuple[bool, str]:
    if image_present(image):
        return True, "already present"

    errors: list[str] = []
    for attempt in range(retries):
        for mirror in PULL_MIRRORS:
            target = f"{mirror}/{image}" if mirror else image
            ok, message = _pull_once(target, timeout)
            if ok:
                if mirror:
                    subprocess.run(["docker", "tag", target, image], capture_output=True, text=True)
                    _docker("rmi", target)
                return True, f"pulled via {mirror or 'default registry'}"
            errors.append(f"[attempt {attempt + 1}] {target}: {message}")
    return False, " | ".join(errors[-3:])


def _remove_our_containers() -> None:
    """Force-remove only containers this harness created (name prefix), never others'."""
    ids = _docker("ps", "-aq", "--filter", "name=minisweagent-").stdout.split()
    if ids:
        _docker("rm", "-f", *ids)


def remove_image(image: str, *, retries: int = 3) -> bool:
    """Remove exactly one image we pulled. Never prune globally on a shared host.

    A finished-run container can briefly still reference the image, which makes
    ``docker rmi`` fail; clear our containers and retry, then verify.
    """
    for _ in range(retries):
        _remove_our_containers()
        _docker("rmi", image)
        if not image_present(image):
            return True
        time.sleep(2)
    return not image_present(image)


def cleanup(env) -> None:
    if cleanup_fn := getattr(env, "cleanup", None):
        cleanup_fn()


# ---------------------------------------------------------------- task evaluation


def _failed(reason: str, detail: str = "") -> VerifyResult:
    return VerifyResult(
        passed=False,
        returncode=-1,
        n_passed=0,
        n_failed=0,
        output=detail or reason,
        duration_s=0.0,
        reward=0.0,
    )


def verify_instance(spec: TaskSpec, timeout: int) -> dict:
    """Independent check: baseline must fail, official patch must pass."""
    env = make_env(spec, "docker")
    try:
        setup = env.execute({"command": spec.setup_command}, timeout=timeout)
        if setup.get("returncode") != 0:
            return {"ok": False, "stage": "setup", "detail": (setup.get("output") or "")[-800:]}

        before = verify(env, spec.test_command, timeout=timeout)
        if before.passed:
            return {"ok": False, "stage": "baseline_should_fail", "detail": before.output[-800:]}

        patch = env.execute({"command": "git apply -v /rrl/gold.patch"}, timeout=timeout)
        if patch.get("returncode") != 0:
            return {"ok": False, "stage": "apply_gold", "detail": (patch.get("output") or "")[-800:]}

        after = verify(env, spec.test_command, timeout=timeout)
        return {
            "ok": after.passed,
            "stage": "done" if after.passed else "gold_should_pass",
            "baseline": {"n_passed": before.n_passed, "n_failed": before.n_failed},
            "after_gold": {"n_passed": after.n_passed, "n_failed": after.n_failed},
            "detail": "" if after.passed else after.output[-800:],
        }
    finally:
        cleanup(env)


def score_patch(spec: TaskSpec, patch: str, timeout: int) -> VerifyResult:
    """Grade an agent patch in a fresh container with the official tests applied."""
    if not patch.strip():
        return _failed("empty_patch")

    blob = base64.b64encode(patch.encode()).decode()
    env = make_env(spec, "docker")
    try:
        apply_agent = env.execute(
            {"command": f"printf '%s' '{blob}' | base64 -d > /tmp/agent.patch && git apply -v /tmp/agent.patch"},
            timeout=timeout,
        )
        if apply_agent.get("returncode") != 0:
            return _failed("agent_patch_apply_failed", (apply_agent.get("output") or "")[-800:])

        apply_tests = env.execute({"command": spec.setup_command}, timeout=timeout)
        if apply_tests.get("returncode") != 0:
            return _failed("test_patch_apply_failed", (apply_tests.get("output") or "")[-800:])

        return verify(env, spec.test_command, timeout=timeout)
    finally:
        cleanup(env)


def run_agent(spec: TaskSpec, model, config: dict, args) -> tuple[object, str]:
    """Run one rollout. The task directory is NOT mounted, so patches stay hidden."""
    env = make_env(spec, "docker", mount_task_dir=False)
    try:
        agent = LoopAgent(
            model,
            env,
            task_id=spec.id,
            system_template=config["system_template"],
            instance_template=config["instance_template"],
            step_limit=args.steps,
            cost_limit=args.cost_limit,
            verifier=None,
            verify_every=0,
        )
        trajectory = agent.run(spec.task)
        diff = env.execute(
            {"command": "cd /testbed && git add -A >/dev/null 2>&1 && git diff --cached"},
            timeout=spec.timeout,
        )
        return trajectory, diff.get("output") or ""
    finally:
        cleanup(env)


# ---------------------------------------------------------------- orchestration


def _append_manifest(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _rejected(path: Path, record: dict) -> None:
    _append_manifest(path, record)


def collect_instance(spec: TaskSpec, model, config: dict, args, out_root: Path, manifest: Path) -> None:
    instance_dir = out_root / spec.id
    instance_dir.mkdir(parents=True, exist_ok=True)

    for k in range(args.rollouts):
        traj_path = instance_dir / f"rollout_{k}.traj.json"
        if traj_path.exists() and not args.force:
            print(f"    rollout {k}: exists, skipping", flush=True)
            continue

        started = time.time()
        trajectory, patch = run_agent(spec, model, config, args)
        (instance_dir / f"rollout_{k}.patch").write_text(patch, encoding="utf-8")

        result = score_patch(spec, patch, spec.timeout)
        trajectory.final = result
        trajectory.save(traj_path)

        record = {
            "instance_id": spec.id,
            "rollout": k,
            "passed": result.passed,
            "reward": result.reward,
            "n_passed": result.n_passed,
            "n_failed": result.n_failed,
            "patch_empty": not patch.strip(),
            "exit_status": trajectory.exit_status,
            "calls": trajectory.n_calls,
            "cost": round(trajectory.cost, 6),
            "steps": len(trajectory.steps),
            "duration_s": round(time.time() - started, 1),
            "trajectory": str(traj_path),
            "patch": str(instance_dir / f"rollout_{k}.patch"),
        }
        _append_manifest(manifest, record)
        print(
            f"    rollout {k}: passed={result.passed} reward={result.reward} "
            f"calls={trajectory.n_calls} cost=${trajectory.cost:.4f}",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", required=True, help="JSONL of instances (train split only)")
    parser.add_argument("--tasks-dir", default=str(ROOT / "tasks/swebench"))
    parser.add_argument("--config", default=str(ROOT / "configs/harness.yaml"))
    parser.add_argument("--model", default="deepseek/deepseek-chat")
    parser.add_argument("--rollouts", type=int, default=1)
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument("--cost-limit", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=None, help="only the first N instances (smoke test)")
    parser.add_argument("--min-free-gb", type=float, default=50.0, help="abort below this much free space on the host disk (GiB)")
    parser.add_argument("--pull-timeout", type=int, default=900, help="seconds before a stalled pull is abandoned")
    parser.add_argument("--keep-images", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--out", default=str(ROOT / "data/trajectories"))
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    split_path = Path(args.split).resolve()
    rows = [json.loads(line) for line in split_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        rows = rows[: args.limit]

    # Guard: never generate training data on evaluation repositories.
    eval_path = ROOT / "data/taskset/eval_verified.jsonl"
    if eval_path.exists():
        eval_repos = {json.loads(line)["repo"] for line in eval_path.read_text(encoding="utf-8").splitlines() if line.strip()}
        leaked = sorted({row["repo"] for row in rows} & eval_repos)
        if leaked:
            sys.exit(f"refusing to run: repos also present in the eval set -> {leaked}")

    by_repo: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_repo[row["repo"]].append(row)

    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    manifest = out_root / "manifest.jsonl"
    rejected = out_root / "rejected.jsonl"

    model = LitellmModel(
        model_name=args.model,
        model_kwargs={"temperature": 0.0, "max_tokens": 4096, "drop_params": True},
    )

    tasks_dir = Path(args.tasks_dir).resolve()
    pulled: list[str] = []

    # All paths are absolute by now; a long Docker run can invalidate a cwd on /mnt/c.
    os.chdir("/")

    try:
        for repo, instances in sorted(by_repo.items()):
            images = [(row["instance_id"], image_name(row["instance_id"])) for row in instances]
            print(f"\n=== {repo} ({len(instances)} instances) ===", flush=True)

            free = disk_free_gb()
            print(f"disk free: {free:.1f} GB", flush=True)
            if free < args.min_free_gb:
                sys.exit(f"aborting: free disk {free:.1f} GB < {args.min_free_gb} GB")

            for instance_id, image in images:
                started_pull = time.time()
                ok, message = pull_image(image, timeout=args.pull_timeout)
                print(f"  pull {instance_id}: {message} ({time.time() - started_pull:.0f}s)", flush=True)
                if not ok:
                    _rejected(rejected, {"instance_id": instance_id, "stage": "pull", "detail": message})
                    continue
                pulled.append(image)

            for instance_id, image in images:
                if not image_present(image):
                    continue
                spec = TaskSpec.load(tasks_dir / instance_id)

                print(f"  validate {instance_id}", flush=True)
                check = verify_instance(spec, spec.timeout)
                if not check["ok"]:
                    print(f"    rejected: {check['stage']}", flush=True)
                    _rejected(rejected, {"instance_id": instance_id, **check})
                    continue

                collect_instance(spec, model, config, args, out_root, manifest)

            if not args.keep_images:
                print(f"  removing {len(images)} images for {repo}", flush=True)
                leftover = [image for _, image in images if not remove_image(image)]
                if leftover:
                    print(f"    WARNING: could not remove: {leftover}", flush=True)
                else:
                    print("    all images removed", flush=True)
                pulled.clear()
    finally:
        if pulled and not args.keep_images:
            print("cleaning up images pulled in this run", flush=True)
            leftover = [image for image in pulled if not remove_image(image)]
            if leftover:
                print(f"WARNING: could not remove: {leftover}", flush=True)


if __name__ == "__main__":
    main()
