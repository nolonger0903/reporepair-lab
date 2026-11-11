"""Download SWE-bench Lite and store it as JSONL for the cleaning pipeline."""

import json
import os
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from datasets import load_dataset  # noqa: E402

OUT = Path("data/raw/swebench_lite")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    print("instances:", len(ds))
    print("columns:", ds.column_names)
    record = ds[0]
    print("sample fields:")
    for key, value in record.items():
        text = str(value).replace("\n", " ")[:160]
        print(f"  {key}: {text}")
    path = OUT / "test.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for row in ds:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("wrote", path, path.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
