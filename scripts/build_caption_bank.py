# scripts/build_caption_bank.py
"""一次性:把 ACE-Step 官方 examples/text2music 的 caption 打标后写入 src/data/caption_bank.json。

用法(项目根目录): .venv/bin/python scripts/build_caption_bank.py [examples_dir]
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config  # noqa: E402
from src.caption_bank import BANK_PATH, detect_gender, tag_caption  # noqa: E402
from src.presets import UI_GENRES  # noqa: E402
from src.textcheck import has_cjk  # noqa: E402


def main(src_dir: str) -> None:
    entries = []
    for path in sorted(glob.glob(os.path.join(src_dir, "*.json"))):
        with open(path, encoding="utf-8") as f:
            cap = (json.load(f).get("caption") or "").strip()
        if not cap or has_cjk(cap):
            continue
        entries.append({"id": os.path.splitext(os.path.basename(path))[0], "caption": cap,
                        "genres": tag_caption(cap), "gender": detect_gender(cap)})
    os.makedirs(os.path.dirname(BANK_PATH), exist_ok=True)
    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump({"source": "ace-step/ACE-Step-1.5 examples/text2music",
                   "license": "MIT", "entries": entries}, f, ensure_ascii=False, indent=1)
    covered = {g for e in entries for g in e["genres"]}
    print(f"{len(entries)} entries -> {BANK_PATH}")
    print(f"genres covered {len(covered)}/{len(UI_GENRES)}; "
          f"missing: {sorted(set(UI_GENRES) - covered)}")


if __name__ == "__main__":
    default = os.path.join(config.ACESTEP_PROJECT_ROOT, "examples", "text2music")
    main(sys.argv[1] if len(sys.argv) > 1 else default)
