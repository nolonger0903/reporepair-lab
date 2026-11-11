"""Core data types shared by the harness."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TaskSpec:
    """A single code-repair task: a repo at a known baseline plus a test command."""

    id: str
    task: str
    repo: Path | None = None
    test_command: str = "python -m pytest -q"
    setup_command: str = ""
    image: str = "python:3.12-slim"
    timeout: int = 300
    workdir: str = "/repo"
    """Working directory inside the container."""
    mount_repo: bool = True
    """Whether to bind-mount ``repo`` into the container. SWE-bench images already contain the repo."""
    task_dir: Path | None = None
    """Directory holding task.md / patches; mounted read-only at /rrl in Docker."""

    @classmethod
    def load(cls, task_dir: str | Path) -> "TaskSpec":
        task_dir = Path(task_dir).resolve()
        meta = yaml.safe_load((task_dir / "task.yaml").read_text(encoding="utf-8"))
        task_file = task_dir / meta.pop("task_file", "task.md")
        repo = meta.pop("repo", "repo")
        repo_path = (task_dir / repo).resolve() if repo else None
        return cls(
            id=meta.pop("id", task_dir.name),
            task=task_file.read_text(encoding="utf-8"),
            repo=repo_path,
            task_dir=task_dir,
            **meta,
        )


@dataclass
class VerifyResult:
    passed: bool
    returncode: int
    n_passed: int
    n_failed: int
    output: str
    duration_s: float
    reward: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "returncode": self.returncode,
            "n_passed": self.n_passed,
            "n_failed": self.n_failed,
            "output": self.output,
            "duration_s": self.duration_s,
            "reward": self.reward,
        }


@dataclass
class StepRecord:
    step: int
    timestamp: float
    actions: list[dict]
    observations: list[dict]
    verify: VerifyResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "timestamp": self.timestamp,
            "actions": self.actions,
            "observations": self.observations,
            "verify": self.verify.to_dict() if self.verify else None,
        }


@dataclass
class Trajectory:
    task_id: str
    model: str
    messages: list[dict]
    steps: list[StepRecord] = field(default_factory=list)
    final: VerifyResult | None = None
    exit_status: str = ""
    submission: str = ""
    cost: float = 0.0
    n_calls: int = 0
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "model": self.model,
            "exit_status": self.exit_status,
            "submission": self.submission,
            "cost": self.cost,
            "n_calls": self.n_calls,
            "duration_s": self.duration_s,
            "final": self.final.to_dict() if self.final else None,
            "steps": [s.to_dict() for s in self.steps],
            "messages": self.messages,
            "trajectory_format": "reporepair-0.1",
        }

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> dict[str, Any]:
        return json.loads(Path(path).read_text(encoding="utf-8"))
