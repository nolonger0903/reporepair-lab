"""Verifiable reward: run the task's test command and turn the result into a reward."""

from __future__ import annotations

import re
import time
from typing import Any

from .protocol import VerifyResult

_NUM = r"(\d+)"
_PASSED = re.compile(_NUM + r" passed")
_FAILED = re.compile(_NUM + r" failed")
_ERROR = re.compile(_NUM + r" error")
_SUMMARY_HINT = re.compile(r"\b\d+ (?:passed|failed|error)")
# Repos such as astropy force ``--color=yes``; the summary then reads
# ``\x1b[1m10 passed\x1b[0m`` and ``\b`` cannot match between ``m`` and ``1``.
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def parse_pytest_counts(line: str) -> tuple[int, int]:
    """Return (n_passed, n_failed) for a single pytest summary line."""
    passed = sum(int(m) for m in _PASSED.findall(line))
    failed = sum(int(m) for m in _FAILED.findall(line))
    failed += sum(int(m) for m in _ERROR.findall(line))
    return passed, failed


def parse_pytest_summary(text: str) -> tuple[int, int]:
    """Counts from the *last* summary line.

    Some suites (pytest's own) spawn nested pytest runs via ``pytester``; their summaries
    appear earlier in the log. Summing every occurrence inflates the counts, so we take
    the final one, which belongs to the top-level run.
    """
    for line in reversed(strip_ansi(text).splitlines()):
        if _SUMMARY_HINT.search(line):
            return parse_pytest_counts(line)
    return 0, 0


def verify(env: Any, test_command: str, *, timeout: int = 300) -> VerifyResult:
    """Execute the test command in an environment and score the outcome.

    Pass/fail is decided by the process return code alone: a nested test runner's output
    must never be able to flip the verdict.
    """
    start = time.time()
    result = env.execute({"command": test_command}, timeout=timeout)
    duration = time.time() - start
    output = result.get("output", "") or ""
    returncode = result.get("returncode", -1)

    n_passed, n_failed = parse_pytest_summary(output)
    ran_any = (n_passed + n_failed) > 0
    # Verdict is returncode-only (see HANDOFF trap #4). ``ran_any`` is kept for the
    # partial-credit score below, but must never override a clean exit: suites that
    # colorize or reformat their summary would otherwise be marked as failures.
    passed = returncode == 0

    # Binary reward is what Phase 5 trains on; partial credit is kept only for analysis.
    reward = 1.0 if passed else 0.0
    if not passed and ran_any:
        reward = 0.25 * n_passed / (n_passed + n_failed)

    return VerifyResult(
        passed=passed,
        returncode=returncode,
        n_passed=n_passed,
        n_failed=n_failed,
        output=output[-8000:],
        duration_s=duration,
        reward=reward,
    )
