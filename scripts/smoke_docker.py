"""Smoke-test a task's Docker environment: mount, setup, and test command."""

import argparse

from reporepair.harness.environment import make_env
from reporepair.harness.protocol import TaskSpec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--backend", default="docker")
    args = parser.parse_args()

    spec = TaskSpec.load(args.task)
    print("image:", spec.image, "| workdir:", spec.workdir, "| mount_repo:", spec.mount_repo)
    env = make_env(spec, args.backend)
    try:
        for label, command in (
            ("pwd+ls", "pwd && ls"),
            ("setup", spec.setup_command),
            ("tests", spec.test_command),
        ):
            if not command:
                print(f"[{label}] skipped")
                continue
            result = env.execute({"command": command}, timeout=spec.timeout)
            print(f"[{label}] returncode={result['returncode']}")
            print((result.get("output") or "")[-800:])
    finally:
        if cleanup := getattr(env, "cleanup", None):
            cleanup()


if __name__ == "__main__":
    main()
