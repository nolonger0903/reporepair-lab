"""Print a compact, human-readable summary of a mini-swe-agent trajectory."""

import json
import sys
from pathlib import Path


def main(path: str) -> None:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    print("trajectory_format:", d.get("trajectory_format"))
    print("top-level keys:", list(d))
    print("info:")
    print(json.dumps(d.get("info", {}), ensure_ascii=False, indent=2)[:1200])
    msgs = d.get("messages", [])
    print(f"\nmessages: {len(msgs)}")
    for i, m in enumerate(msgs):
        role = m.get("role", "?")
        content = m.get("content") or ""
        extra = m.get("extra") or {}
        calls = m.get("tool_calls") or []
        obs = extra.get("actions") or []
        print(
            f"[{i:>2}] {role:<9} chars={len(content):>5} tool_calls={len(calls)} "
            f"actions={len(obs)} extra={sorted(extra)}"
        )
        if role == "assistant":
            for c in calls:
                print(f"      -> {json.dumps(c.get('function', {}).get('arguments', ''), ensure_ascii=False)[:150]}")
            if extra.get("cost") is not None:
                print(f"      cost={extra.get('cost'):.6f} tokens={extra.get('response', {}).get('usage')}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / ".config/mini-swe-agent/last_mini_run.traj.json"))
