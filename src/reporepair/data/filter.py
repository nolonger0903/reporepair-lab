"""Trajectory cleaning: filtering, de-duplication, and SFT-ready export."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def load_many(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]


def command_sequence(traj: dict[str, Any]) -> list[str]:
    return [
        action.get("command", "")
        for step in traj.get("steps", [])
        for action in step.get("actions", [])
    ]


def signature(traj: dict[str, Any]) -> str:
    """Two runs that executed the same commands are treated as duplicates."""
    payload = "\n".join(command_sequence(traj)).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def filter_trajectories(
    trajs: Iterable[dict[str, Any]],
    *,
    require_pass: bool = True,
    allowed_status: set[str] | None = None,
    max_cost: float | None = None,
    max_steps: int | None = None,
    min_steps: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Keep usable trajectories and report why the rest were dropped."""
    kept: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}

    def drop(reason: str) -> None:
        reasons[reason] = reasons.get(reason, 0) + 1

    for traj in trajs:
        final = traj.get("final") or {}
        n_steps = len(traj.get("steps", []))
        if require_pass and not final.get("passed"):
            drop("not_passed")
            continue
        if allowed_status is not None and traj.get("exit_status") not in allowed_status:
            drop("exit_status")
            continue
        if max_cost is not None and traj.get("cost", 0.0) > max_cost:
            drop("cost")
            continue
        if max_steps is not None and n_steps > max_steps:
            drop("steps")
            continue
        if n_steps < min_steps:
            drop("too_short")
            continue
        kept.append(traj)
    return kept, reasons


def dedup_trajectories(trajs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Drop trajectories that executed the same command sequence.

    Keeps the cheapest instance of each signature group.
    """
    groups: dict[str, dict[str, Any]] = {}
    for traj in trajs:
        sig = signature(traj)
        current = groups.get(sig)
        if current is None or traj.get("cost", 0.0) < current.get("cost", 0.0):
            groups[sig] = traj
    kept = list(groups.values())
    return kept, len(trajs) - len(kept)


def to_sft_messages(traj: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a harness trajectory into plain chat messages.

    Internal ``extra`` blobs are stripped. The terminal ``exit`` message is dropped:
    it is harness scaffolding, not model output, and must never become a training target.

    Assistant messages use native tool calls (empty ``content`` + ``tool_calls``), so the
    matching ``tool_call_id`` on tool messages must be preserved or the conversation is
    malformed and cannot be trained on.
    """
    messages = []
    for message in traj.get("messages", []):
        role = message.get("role")
        if role == "exit":
            continue
        clean: dict[str, Any] = {"role": role, "content": message.get("content", "")}
        if message.get("tool_calls"):
            clean["tool_calls"] = message["tool_calls"]
        if message.get("tool_call_id"):
            clean["tool_call_id"] = message["tool_call_id"]
        messages.append(clean)
    return messages


def export_sft(trajs: Iterable[dict[str, Any]], path: str | Path) -> int:
    """Write one JSONL record per trajectory, in chat-message form."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for traj in trajs:
            record = {
                "task_id": traj.get("task_id"),
                "reward": (traj.get("final") or {}).get("reward"),
                "messages": to_sft_messages(traj),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            n += 1
    return n
