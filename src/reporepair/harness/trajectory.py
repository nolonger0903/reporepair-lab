"""Trajectory utilities: summarising and deterministic replay."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def iter_actions(traj: dict[str, Any]):
    for step in traj.get("steps", []):
        for action in step.get("actions", []):
            yield step["step"], action


def replay(traj: dict[str, Any], env, *, reset: Callable[[], None] | None = None) -> list[dict[str, Any]]:
    """Re-execute every recorded action in ``env`` and collect fresh observations.

    ``reset`` should restore the repo to its baseline commit so the replay starts
    from the same state the original run did.
    """
    if reset:
        reset()
    results = []
    for step, action in iter_actions(traj):
        try:
            output = env.execute(action)
            error = None
        except Exception as e:  # Submitted and friends end the replay
            output, error = None, f"{type(e).__name__}: {e}"
        results.append({"step": step, "action": action, "observation": output, "error": error})
        if error:
            break
    return results


def compare_replay(original: dict[str, Any], replayed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag steps where the replay's return code differs from the original."""
    diffs = []
    original_obs = [obs for step in original.get("steps", []) for obs in step.get("observations", [])]
    for i, item in enumerate(replayed):
        if i >= len(original_obs):
            break
        before = original_obs[i].get("returncode")
        after = (item["observation"] or {}).get("returncode")
        if before != after:
            diffs.append({"index": i, "step": item["step"], "original": before, "replayed": after})
    return diffs


def load(path: str | Path) -> dict[str, Any]:
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))
