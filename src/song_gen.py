import os

from src.spec import SongSpec

_LENGTH_MAP = {"short": 45, "full": 210}
# ACE-Step 1.5 turbo 模型推荐推理步数=8（base 模型建议 32-64）。
_INFER_STEP = 8
# turbo 模型推荐 shift=3.0（base 用默认 1.0）。
_SHIFT = 3.0

# 模型很重，进程内只初始化一次，之后复用。
_dit_handler = None
_llm_handler = None


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


def _get_handlers():
    """惰性初始化 ACE-Step 1.5 的 DiT 与 5Hz-LM handler（仅一次）。"""
    global _dit_handler, _llm_handler
    if _dit_handler is not None and _llm_handler is not None:
        return _dit_handler, _llm_handler

    import config
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler

    device = config.get_device()
    dit = AceStepHandler()
    dit.initialize_service(
        project_root=config.ACESTEP_PROJECT_ROOT,
        config_path=config.ACESTEP_CONFIG,
        device=device,
    )
    llm = LLMHandler()
    llm.initialize(
        checkpoint_dir=config.ACESTEP_CHECKPOINT_DIR,
        lm_model_path=config.ACESTEP_LM_MODEL,
        backend=config.acestep_backend(device),
        device=device,
    )
    _dit_handler, _llm_handler = dit, llm
    return dit, llm


def generate_song(structured_lyrics: str, spec: SongSpec, *,
                  length: str = "full", seed: int | None = None, out_path: str) -> str:
    """惰性 import ACE-Step 1.5 并生成歌曲，返回实际产出的音频路径。

    对接 ACE-Step 1.5 官方 Python API（acestep.inference.generate_music）。
    ⚠ 集成点：config.ACESTEP_* 路径为机器相关，需在 Colab 冒烟测试时以实际
    clone/权重下载位置校准；权重首次运行自动下载。
    """
    from acestep.inference import GenerationParams, GenerationConfig, generate_music

    p = build_acestep_params(spec, length=length, seed=seed)
    dit, llm = _get_handlers()

    fixed = seed is not None
    params = GenerationParams(
        caption=p["prompt"],
        lyrics=structured_lyrics,
        duration=float(p["duration"]),
        bpm=p["bpm"],
        vocal_language=p["language"],
        seed=seed if fixed else -1,
        inference_steps=_INFER_STEP,
        shift=_SHIFT,
    )
    gen_config = GenerationConfig(
        batch_size=1,
        audio_format="wav",
        use_random_seed=not fixed,
        seeds=[seed] if fixed else None,
    )

    save_dir = os.path.dirname(out_path) or "."
    result = generate_music(dit, llm, params, gen_config, save_dir=save_dir)
    if not result.success or not result.audios:
        raise RuntimeError(f"ACE-Step 生成失败: {result.error or '无音频输出'}")
    return result.audios[0]["path"]
