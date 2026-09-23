import inspect
import os
import sys

from src.presets import get_preset
from src.spec import SongSpec

_LENGTH_MAP = {"short": 45, "full": 210}
# ACE-Step 1.5 turbo 模型推荐推理步数=8（base 模型建议 32-64）。
_INFER_STEP = 8
# turbo 模型推荐 shift=3.0(官方评价:语义强、清晰,但偏"干"、配器极简)。
# 优先级:环境变量 ACESTEP_SHIFT > preset.acestep.shift > 3.0,便于不改代码做 A/B。
_DEFAULT_SHIFT = 3.0


def resolve_shift(preset_id: str) -> float:
    env = os.environ.get("ACESTEP_SHIFT", "").strip()
    if env:
        return float(env)
    try:
        return float(get_preset(preset_id).acestep.shift)
    except ValueError:
        return _DEFAULT_SHIFT

# ── MPS 省内存补丁:prefill 只算最后一个位置的 logits ────────────────
#
# ACE-Step 的自定义 CFG 解码循环(llm_inference._forward_pass)首个 forward 传
# 整段 prompt 却不带 logits_to_keep,transformers 于是给每个 prompt token 都算
# 了一遍全词表 logits。MPS 上这块特别贵:上游把 LM 强制成 float32
# (llm_inference.initialize,bf16 权重转 fp16 会 NaN),5Hz LM 词表 217204,
# CFG 又把 batch 变成 2(条件+无条件) —— 2 × 217204 × 4B ≈ 1.66 MiB / token,
# 747 token 的歌词一次就要 1.21 GiB,16GB 机器上直接 MPS OOM,且随歌词长度线性
# 增长。而两个调用点(llm_inference.py:2570 / 2684)都只取 outputs.logits[:, -1, :]。
# 传 logits_to_keep=1 语义等价,峰值从 GiB 级降到 MB 级,顺带 prefill 变快。
#
# 补丁打在我们这边而不是改 ACE-Step 源码:那是独立 clone 的上游仓库,改了会在
# 下次 git pull 时丢掉或冲突。
_LOGITS_TO_KEEP_SUPPORT: dict[type, bool] = {}


def _supports_logits_to_keep(model) -> bool:
    """模型 forward 是否显式接受 logits_to_keep。结果按类缓存(每步都要问)。"""
    cls = type(model)
    cached = _LOGITS_TO_KEEP_SUPPORT.get(cls)
    if cached is None:
        try:
            cached = "logits_to_keep" in inspect.signature(cls.forward).parameters
        except (TypeError, ValueError):
            cached = False
        _LOGITS_TO_KEEP_SUPPORT[cls] = cached
    return cached


def patch_prefill_logits(llm_cls) -> bool:
    """给 LLMHandler._forward_pass 打补丁,返回是否真的打上了。

    幂等:重复调用只打一次。不认识的 handler(没有 _forward_pass,比如测试里的
    假对象)原样放过 —— 这是纯优化,缺了它只是更费内存,不该让出歌失败。
    """
    orig = getattr(llm_cls, "_forward_pass", None)
    if orig is None or getattr(orig, "_ze_prefill_patch", False):
        return False

    def _forward_pass(self, model, generated_ids, model_kwargs, past_key_values, use_cache):
        # 只有 prefill(还没有 KV cache)才会一次喂进整段 prompt;增量解码那支
        # 喂的是 generated_ids[:, -1:],logits 本来就只有一个位置。
        if past_key_values is None and _supports_logits_to_keep(model):
            return model(
                input_ids=generated_ids,
                **model_kwargs,
                use_cache=use_cache,
                logits_to_keep=1,
            )
        return orig(self, model, generated_ids, model_kwargs, past_key_values, use_cache)

    _forward_pass._ze_prefill_patch = True
    llm_cls._forward_pass = _forward_pass
    return True


# 模型很重，进程内只初始化一次，之后复用。
_dit_handler = None
_llm_handler = None


def build_acestep_params(spec: SongSpec, length: str = "full", seed: int | None = None) -> dict:
    tags = [*spec.genre, *spec.mood, *spec.instrument,
            f"{spec.vocal.gender} vocal", spec.vocal.style]
    tag_string = ", ".join(t for t in tags if t)
    # 有 planner 写的英文整句就用它并关掉 LM 重写(DeepSeek 的音乐知识 ≫ 本机 0.6B);
    # 否则退回标签串并让 5Hz LM 扩写。
    caption = spec.caption or tag_string
    return {
        "prompt": caption,      # 兼容旧调用方
        "caption": caption,
        "use_cot_caption": not spec.caption_full,
        "keyscale": spec.keyscale or "",
        "timesignature": str(spec.timesignature) if spec.timesignature else "",
        "shift": resolve_shift(spec.preset_id),
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

    # ACE-Step 由官方源码独立管理环境；将其源码根目录加入模块搜索路径，
    # 无需把项目本身重复安装进应用环境。
    if config.ACESTEP_PROJECT_ROOT not in sys.path:
        sys.path.insert(0, config.ACESTEP_PROJECT_ROOT)
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler

    patch_prefill_logits(LLMHandler)

    # 官方示例(run_generate_test.py)对 device 传 "auto" 让其自动探测;
    # backend 仍按本机探测到的设备选(cuda->vllm, mps->mlx, 其余->pt)。
    # 两个 initialize 都返回 (消息, 是否成功) 而不是抛异常。返回值必须检查:
    # 丢掉它们会让 5Hz LM 静默不启动(日志里只留一行 llm_initialized=False),
    # 出歌看起来照常"成功",但实际是没有 CoT 规划的裸 DiT。
    detected = config.get_device()
    offload = config.acestep_offload(detected)
    dit = AceStepHandler()
    msg, ok = dit.initialize_service(
        project_root=config.ACESTEP_PROJECT_ROOT,
        config_path=config.ACESTEP_CONFIG,
        device="auto",
        offload_to_cpu=offload,
    )
    if not ok:
        raise RuntimeError(f"ACE-Step DiT 初始化失败: {msg}")
    llm = LLMHandler()
    msg, ok = llm.initialize(
        checkpoint_dir=config.ACESTEP_CHECKPOINT_DIR,
        lm_model_path=config.ACESTEP_LM_MODEL,
        backend=config.acestep_backend(detected),
        device="auto",
        offload_to_cpu=offload,
    )
    if not ok:
        raise RuntimeError(f"ACE-Step 5Hz LM 初始化失败: {msg}")
    # 只有两者都成功才写全局,否则坏 handler 会被缓存并一直复用。
    _dit_handler, _llm_handler = dit, llm
    return dit, llm


def _fake_song(length: str, out_path: str) -> str:
    """dev 专用：用 ffmpeg 造一段正弦音代替真出歌(验证下游链路)。"""
    import subprocess

    dur = 8 if length == "short" else 12
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    cmd = ["ffmpeg", "-y", "-f", "lavfi",
           "-i", f"sine=frequency=440:duration={dur}", out_path]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"假音频生成失败: {(proc.stderr or b'').decode(errors='ignore')[:200]}"
        )
    return out_path


def generate_song(structured_lyrics: str, spec: SongSpec, *,
                  length: str = "full", seed: int | None = None, out_path: str) -> str:
    """惰性 import ACE-Step 1.5 并生成歌曲，返回实际产出的音频路径。

    对接 ACE-Step 1.5 官方 Python API（acestep.inference.generate_music）。
    ⚠ 集成点：config.ACESTEP_* 路径为机器相关，需在 Colab 冒烟测试时以实际
    clone/权重下载位置校准；权重首次运行自动下载。

    dev 专用：设 ZE_FAKE_GEN=1 时不跑 ACE-Step，用 ffmpeg 造一段正弦音，
    用来验证下游链路（MP3/R2/DB/前端播放），不影响真实出歌路径。
    """
    if os.environ.get("ZE_FAKE_GEN"):
        return _fake_song(length, out_path)

    import config

    if config.ACESTEP_PROJECT_ROOT not in sys.path:
        sys.path.insert(0, config.ACESTEP_PROJECT_ROOT)
    from acestep.inference import GenerationParams, GenerationConfig, generate_music

    p = build_acestep_params(spec, length=length, seed=seed)
    dit, llm = _get_handlers()

    fixed = seed is not None
    params = GenerationParams(
        caption=p["caption"],
        lyrics=structured_lyrics,
        duration=float(p["duration"]),
        bpm=p["bpm"],
        keyscale=p["keyscale"],
        timesignature=p["timesignature"],
        vocal_language=p["language"],
        seed=seed if fixed else -1,
        inference_steps=_INFER_STEP,
        shift=p["shift"],
        thinking=True,
        use_cot_caption=p["use_cot_caption"],
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
