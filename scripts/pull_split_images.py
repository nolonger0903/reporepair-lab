"""Pull the images for a split, reusing collect.py's mirror fallback."""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect import pull_image  # noqa: E402
from reporepair.tasks.swebench import image_name  # noqa: E402

split = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data/taskset/eval_candidates.jsonl")
rows = [json.loads(l) for l in split.read_text(encoding="utf-8").splitlines() if l.strip()]

failed = []
for i, row in enumerate(rows, 1):
    image = image_name(row["instance_id"])
    t0 = time.time()
    ok, message = pull_image(image, timeout=900)
    print(f"[{i}/{len(rows)}] {row['instance_id']}: {message} ({time.time() - t0:.0f}s)", flush=True)
    if not ok:
        failed.append(row["instance_id"])

print("failed:", failed)
