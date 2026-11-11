"""Turn a SWE-bench instance into a task directory on disk."""

from __future__ import annotations

from pathlib import Path

import yaml

from . import swebench


def materialize(instance: dict, out_dir: Path) -> Path:
    """Write task.md / task.yaml / gold.patch / test.patch for one instance."""
    task_dir = out_dir / instance["instance_id"]
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.md").write_text(instance["problem_statement"].strip() + "\n", encoding="utf-8")
    (task_dir / "gold.patch").write_text(instance["patch"], encoding="utf-8")
    (task_dir / "test.patch").write_text(instance["test_patch"], encoding="utf-8")

    setup_command, test_command = swebench.build_commands(instance)
    meta = {
        "id": instance["instance_id"],
        "task_file": "task.md",
        "repo": "",
        "test_command": test_command,
        "setup_command": setup_command,
        "image": swebench.image_name(instance["instance_id"]),
        "timeout": 900,
        "workdir": "/testbed",
        "mount_repo": False,
    }
    (task_dir / "task.yaml").write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return task_dir
