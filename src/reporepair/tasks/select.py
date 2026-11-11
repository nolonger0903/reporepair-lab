"""Filtering, de-duplication and leakage-safe splitting of a task pool."""

from __future__ import annotations

import random
import re
from typing import Any, Iterable

_TOKEN = re.compile(r"[a-z0-9_]+")


def tokens(text: str) -> set[str]:
    return set(_TOKEN.findall((text or "").lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def filter_pool(
    instances: Iterable[dict[str, Any]],
    *,
    repos: set[str] | None = None,
    min_chars: int = 200,
    max_chars: int = 6000,
) -> list[dict[str, Any]]:
    """Keep instances that are well-formed and cheap enough to run."""
    kept = []
    for inst in instances:
        if repos is not None and inst["repo"] not in repos:
            continue
        statement = inst.get("problem_statement") or ""
        if not (min_chars <= len(statement) <= max_chars):
            continue
        if not inst.get("patch") or not inst.get("test_patch"):
            continue
        if not inst.get("FAIL_TO_PASS"):
            continue
        kept.append(inst)
    return kept


def dedup(instances: list[dict[str, Any]], *, threshold: float = 0.85) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Drop near-duplicate problem statements within the same repo. Returns (kept, dropped)."""
    kept: list[dict[str, Any]] = []
    kept_tokens: list[set[str]] = []
    dropped: list[dict[str, Any]] = []
    for inst in instances:
        current = tokens(inst["problem_statement"])
        is_dup = any(
            inst["repo"] == other["repo"] and jaccard(current, other_tokens) > threshold
            for other, other_tokens in zip(kept, kept_tokens)
        )
        if is_dup:
            dropped.append(inst)
        else:
            kept.append(inst)
            kept_tokens.append(current)
    return kept, dropped


def split_by_repo(
    instances: list[dict[str, Any]], *, eval_ratio: float = 0.25, seed: int = 0
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split on repo boundaries so no repository appears in both train and eval."""
    repos = sorted({inst["repo"] for inst in instances})
    random.Random(seed).shuffle(repos)
    n_eval = max(1, round(len(repos) * eval_ratio))
    eval_repos = set(repos[:n_eval])
    train = [inst for inst in instances if inst["repo"] not in eval_repos]
    evaluation = [inst for inst in instances if inst["repo"] in eval_repos]
    return train, evaluation


def sample(instances: list[dict[str, Any]], n: int, *, seed: int = 0) -> list[dict[str, Any]]:
    if n >= len(instances):
        return list(instances)
    return sorted(random.Random(seed).sample(instances, n), key=lambda i: i["instance_id"])


def stratified_sample(instances: list[dict[str, Any]], n: int, *, seed: int = 0) -> list[dict[str, Any]]:
    """Sample proportionally across repos so a large repo does not dominate."""
    by_repo: dict[str, list[dict[str, Any]]] = {}
    for inst in instances:
        by_repo.setdefault(inst["repo"], []).append(inst)
    rng = random.Random(seed)
    ordered_repos = sorted(by_repo)
    total = len(instances)
    picked: list[dict[str, Any]] = []
    for i, repo in enumerate(ordered_repos):
        pool = sorted(by_repo[repo], key=lambda x: x["instance_id"])
        if i == len(ordered_repos) - 1:
            quota = n - len(picked)
        else:
            quota = round(n * len(pool) / total)
        quota = max(1, min(quota, len(pool)))
        picked.extend(rng.sample(pool, quota))
    return sorted(picked[:n], key=lambda i: i["instance_id"])
