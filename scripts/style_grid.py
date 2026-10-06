# scripts/style_grid.py
"""风格网格评测:同一段歌词 × 14 个曲风 × 固定 seed,只跑 识别/采样/planner(不出歌)。

用法(项目根目录,需 .env 里的 LLM key):
  set -a; . ./.env; set +a
  .venv/bin/python scripts/style_grid.py [--seed 1001] [--creativity normal]
"""
import argparse
import itertools
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config  # noqa: E402
from src import planner  # noqa: E402
from src.presets import UI_GENRES, get_preset  # noqa: E402
from src.style_sampler import sample_style  # noqa: E402

STOP = {"a", "an", "the", "and", "with", "of", "in", "on", "over", "by", "its", "is", "to",
        "that", "as", "into", "for"}


def tokens(caption: str) -> set[str]:
    return {t for t in re.findall(r"[a-z][a-z&'-]+", caption.lower()) if t not in STOP}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--creativity", default="normal")
    args = ap.parse_args()

    opts = {"provider": config.LLM_PROVIDER}
    rows, caps, hits, degraded = [], [], 0, 0
    for pid in UI_GENRES:
        preset = get_preset(pid)
        draw = sample_style(preset, seed=args.seed, creativity=args.creativity)
        events: list[dict] = []
        spec = planner.plan_song("", preset=preset, draw=draw, llm_options=opts,
                                 status_events=events)
        hit = any(k in spec.caption.lower() for k in preset.caption_keywords)
        hits += hit
        degraded += any(not e["ok"] for e in events)
        caps.append(spec.caption)
        rows.append(f"| {preset.label} | {draw.vocal_timbre} | {', '.join(draw.instruments)} "
                    f"| {'✓' if hit else '✗'} | {spec.caption[:120]} |")

    jac = [len(tokens(a) & tokens(b)) / len(tokens(a) | tokens(b))
           for a, b in itertools.combinations(caps, 2)]
    print("| 曲风 | 音色 | 乐器 | 命中 | caption(前 120 字) |\n|---|---|---|---|---|")
    print("\n".join(rows))
    print(f"\n曲风命中率: {hits}/{len(UI_GENRES)}")
    print(f"降级率: {degraded}/{len(UI_GENRES)}")
    print(f"两两 Jaccard 均值: {statistics.mean(jac):.3f}")


if __name__ == "__main__":
    main()
