"""Summarize a RepoRepair-Lab trajectory file."""

import json
import sys


def main(path: str) -> None:
    data = json.load(open(path, encoding="utf-8"))
    print("format:", data.get("trajectory_format"), "| keys:", list(data))
    print("model:", data.get("model"), "| exit:", data.get("exit_status"))
    print("calls:", data.get("n_calls"), "| cost:", data.get("cost"), "| seconds:", round(data.get("duration_s", 0), 1))
    print("steps:", len(data.get("steps", [])), "| messages:", len(data.get("messages", [])))
    for step in data.get("steps", []):
        verify = step.get("verify")
        vtext = "none" if not verify else f"passed={verify['passed']} ({verify['n_passed']}p/{verify['n_failed']}f)"
        print(f"  step {step['step']}: actions={len(step['actions'])} verify={vtext}")
        for action in step["actions"]:
            command = (action.get("command") or "").splitlines()
            print(f"      $ {(command[0] if command else '')[:110]}")
    final = data.get("final") or {}
    print("final:", {k: final.get(k) for k in ("passed", "n_passed", "n_failed", "reward")})
    print("submission:", repr(data.get("submission", "")))


if __name__ == "__main__":
    main(sys.argv[1])
