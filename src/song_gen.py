from src.spec import SongSpec

_LENGTH_MAP = {"short": 45, "full": 210}


def build_acestep_params(spec: SongSpec, length: str = "full", seed: int | None = None) -> dict:
    tags = [*spec.genre, *spec.mood, *spec.instrument,
            f"{spec.vocal.gender} vocal", spec.vocal.style]
    return {
        "prompt": ", ".join(t for t in tags if t),
        "duration": _LENGTH_MAP.get(length, _LENGTH_MAP["full"]),
        "bpm": spec.bpm,
        "language": spec.language,
        "seed": seed,
    }


def generate_song(structured_lyrics: str, spec: SongSpec, *,
                  length: str = "full", seed: int | None = None, out_path: str) -> str:
    """惰性 import ACE-Step 1.5 并生成歌曲，保存到 out_path 后返回。
    ⚠ 集成点：以 Colab 上 `pip show` 出来的 ACE-Step 1.5 实际 API 为准，
    在 Step 4(Colab 冒烟) 时对照官方 README 调整下面的调用签名。
    """
    from config import get_device
    params = build_acestep_params(spec, length=length, seed=seed)

    # 下面为对接占位：按 ACE-Step 1.5 README 的推理入口替换。
    from acestep.pipeline_ace_step import ACEStepPipeline  # 名称以官方为准
    pipe = ACEStepPipeline(device=get_device())
    pipe(
        prompt=params["prompt"],
        lyrics=structured_lyrics,
        audio_duration=params["duration"],
        infer_step=27,
        manual_seeds=str(params["seed"]) if params["seed"] is not None else None,
        save_path=out_path,
    )
    return out_path
