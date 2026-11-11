import sys

from minisweagent.environments.local import LocalEnvironment

from reporepair.harness.reward import parse_pytest_counts, parse_pytest_summary, verify

PYTEST = f'"{sys.executable}" -m pytest -q'


def test_parse_pytest_counts():
    assert parse_pytest_counts("7 passed in 0.08s") == (7, 0)
    assert parse_pytest_counts("3 failed, 4 passed in 0.21s") == (4, 3)
    assert parse_pytest_counts("2 errors, 1 passed") == (1, 2)
    assert parse_pytest_counts("no tests ran in 0.01s") == (0, 0)


def test_summary_uses_last_line_not_nested_runs():
    # pytest's own suite spawns nested pytest runs; their summaries appear first.
    output = "1 passed in 0.01s\nPASSED testing/test_x.py\n3 failed, 4 passed in 0.21s\n"
    assert parse_pytest_summary(output) == (4, 3)


def test_summary_ignores_output_without_a_summary():
    assert parse_pytest_summary("FAILED something\n") == (0, 0)


def test_summary_parses_ansi_colored_output():
    # astropy forces --color=yes: the digits are preceded by an escape ending in "m",
    # which is a word character, so a bare \b\d+ regex never matches.
    line = "\x1b[32m\x1b[32m\x1b[1m10 passed\x1b[0m\x1b[32m in 0.03s\x1b[0m"
    assert parse_pytest_summary(line) == (10, 0)
    assert parse_pytest_counts(line) == (10, 0)


def test_verify_passes_colored_output_with_zero_returncode():
    line = "\x1b[32m\x1b[32m\x1b[1m10 passed\x1b[0m\x1b[32m in 0.03s\x1b[0m\n"
    result = verify(_FakeEnv(line, 0), "pytest")
    assert result.passed is True
    assert (result.n_passed, result.n_failed) == (10, 0)


class _FakeEnv:
    def __init__(self, output: str, returncode: int):
        self.output = output
        self.returncode = returncode

    def execute(self, action, timeout=None):
        return {"output": self.output, "returncode": self.returncode}


def test_verify_trusts_returncode_over_nested_summaries():
    # A nested pytester run reports "1 passed"; the top-level run reports "70 passed".
    output = "1 passed in 0.01s\nPASSED x\n70 passed in 2.74 seconds\n"
    result = verify(_FakeEnv(output, 0), "pytest")
    assert result.passed is True
    assert (result.n_passed, result.n_failed) == (70, 0)


def test_verify_fails_when_returncode_is_nonzero():
    output = "70 passed in 2.74 seconds\n"
    result = verify(_FakeEnv(output, 1), "pytest")
    assert result.passed is False
    assert result.reward < 1.0


def test_verify_rewards_pass_and_fail(tmp_path):
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    env = LocalEnvironment(cwd=str(tmp_path))

    ok = verify(env, PYTEST)
    assert ok.passed is True
    assert ok.reward == 1.0
    assert (ok.n_passed, ok.n_failed) == (1, 0)

    (tmp_path / "test_bad.py").write_text("def test_bad():\n    assert False\n")
    bad = verify(env, PYTEST)
    assert bad.passed is False
    assert bad.reward < 1.0
    assert (bad.n_passed, bad.n_failed) == (1, 1)
