"""SWE-bench instance handling: loading, image names, and per-instance test commands."""

from __future__ import annotations

import ast
import base64
import json
from pathlib import Path
from typing import Any

PYTEST_REPOS = frozenset(
    {
        "astropy/astropy",
        "matplotlib/matplotlib",
        "mwaskom/seaborn",
        "pallets/flask",
        "psf/requests",
        "pydata/xarray",
        "pylint-dev/pylint",
        "pytest-dev/pytest",
        "scikit-learn/scikit-learn",
        "sphinx-doc/sphinx",
    }
)

# SWE-bench images keep the checked-out repo in a conda env named "testbed" at /testbed.
# Some images already put that env on PATH, so activating is best-effort rather than required.
CONDA_ACTIVATE = (
    "if [ -f /opt/miniconda3/etc/profile.d/conda.sh ]; then "
    "source /opt/miniconda3/etc/profile.d/conda.sh && conda activate testbed; fi"
)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def image_name(instance_id: str, *, namespace: str = "swebench", tag: str = "latest") -> str:
    """Docker Hub forbids double underscores, so SWE-bench encodes them as _1776_."""
    return f"{namespace}/sweb.eval.x86_64.{instance_id.lower()}:{tag}".replace("__", "_1776_")


def as_list(value: Any) -> list[str]:
    """SWE-bench stores FAIL_TO_PASS / PASS_TO_PASS as JSON-encoded strings, not lists."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        parsed = ast.literal_eval(value)
    return [str(v) for v in parsed]


def test_ids(instance: dict[str, Any]) -> list[str]:
    return as_list(instance.get("FAIL_TO_PASS")) + as_list(instance.get("PASS_TO_PASS"))


def has_unselectable_ids(instance: dict[str, Any]) -> bool:
    """True if any node id cannot be passed to pytest verbatim.

    SWE-bench ids were extracted from multi-line pytest output, so a few are truncated
    mid-parameter: they may contain a literal ``\\n``, or have unbalanced brackets like
    ``test_x[(AttributeError,``. The container's real id is longer, so the test can never
    be selected -- such instances are excluded rather than silently mis-graded.
    """
    for test_id in test_ids(instance):
        if "\\n" in test_id or "\n" in test_id:
            return True
        if test_id.count("[") != test_id.count("]"):
            return True
    return False


def pytest_command(ids: list[str]) -> str:
    """Run exactly the given node ids via a base64 JSON blob.

    Node ids can contain newlines and quotes (parametrised tests), so neither shell
    quoting nor newline separation is safe -- JSON round-trips them exactly.
    """
    blob = base64.b64encode(json.dumps(ids).encode()).decode()
    return (
        'python -c "import base64,json,pytest,sys; '
        f"ids=json.loads(base64.b64decode('{blob}').decode()); "
        "sys.exit(pytest.main(['-q','-rA',*ids]))\""
    )


def build_commands(instance: dict[str, Any]) -> tuple[str, str]:
    """Return (setup_command, test_command) for a SWE-bench instance."""
    setup = f"{CONDA_ACTIVATE} && git apply -v /rrl/test.patch"
    test = f"{CONDA_ACTIVATE} && {pytest_command(test_ids(instance))}"
    return setup, test
