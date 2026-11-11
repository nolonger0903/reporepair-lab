from reporepair.data.filter import (
    dedup_trajectories,
    filter_trajectories,
    signature,
    to_sft_messages,
)


def _traj(commands, *, passed=True, cost=0.1, status="Submitted"):
    return {
        "task_id": "t",
        "exit_status": status,
        "cost": cost,
        "final": {"passed": passed, "reward": 1.0 if passed else 0.0},
        "steps": [
            {"step": i + 1, "actions": [{"command": c}], "observations": []}
            for i, c in enumerate(commands)
        ],
        "messages": [
            {"role": "system", "content": "s", "extra": {"x": 1}},
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a", "tool_calls": [{"id": "1"}], "extra": {"cost": 0.1}},
            {"role": "tool", "content": "o", "tool_call_id": "1", "extra": {"returncode": 0}},
            {"role": "exit", "content": "", "extra": {"exit_status": "Submitted"}},
        ],
    }


def test_filter_trajectories_drops_failures_and_reports_reasons():
    kept, reasons = filter_trajectories([_traj(["a"]), _traj(["b"], passed=False)])
    assert len(kept) == 1
    assert reasons == {"not_passed": 1}


def test_filter_respects_cost_and_status():
    trajs = [_traj(["a"], cost=5.0), _traj(["b"], status="LimitsExceeded")]
    kept, reasons = filter_trajectories(trajs, max_cost=1.0, allowed_status={"Submitted"})
    assert kept == []
    assert reasons == {"exit_status": 1, "cost": 1}


def test_dedup_keeps_cheapest_of_identical_command_sequences():
    kept, n_dropped = dedup_trajectories([_traj(["a", "b"], cost=0.5), _traj(["a", "b"], cost=0.1)])
    assert n_dropped == 1
    assert kept[0]["cost"] == 0.1


def test_to_sft_messages_strips_extras_and_exit():
    messages = to_sft_messages(_traj(["a"]))
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool"]
    assert all("extra" not in m for m in messages)
    assert messages[2]["tool_calls"] == [{"id": "1"}]
    # Native tool calls: the tool reply must stay linked to its call.
    assert messages[3]["tool_call_id"] == "1"


def test_signature_is_order_sensitive():
    assert signature(_traj(["a", "b"])) != signature(_traj(["b", "a"]))
