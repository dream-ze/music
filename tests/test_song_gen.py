import sys
import types

import pytest

from src import song_gen
from src.song_gen import build_acestep_params
from src.spec import safe_spec


def test_length_short_maps_to_short_duration():
    p = build_acestep_params(safe_spec(), length="short")
    assert p["duration"] == 45


def test_length_full_maps_to_full_duration():
    p = build_acestep_params(safe_spec(), length="full")
    assert p["duration"] == 210


def test_prompt_contains_genre_and_instrument():
    spec = safe_spec()  # genre=[mandopop], instrument=[piano, soft drums], mood=[warm], vocal=gender='female' style='soft'
    p = build_acestep_params(spec)
    assert "mandopop" in p["prompt"]
    assert "piano" in p["prompt"]
    assert "warm" in p["prompt"]
    assert "female vocal" in p["prompt"]


def test_seed_passthrough():
    p = build_acestep_params(safe_spec(), seed=123)
    assert p["seed"] == 123


def test_language_key_in_params():
    p = build_acestep_params(safe_spec())
    assert p["language"] == safe_spec().language
    assert p["language"] == "zh"


# ── handler 初始化:失败必须显式抛错,不能静默降级 ──────────────────
#
# ACE-Step 的 initialize_service / initialize 都返回 (消息, 是否成功) 而不是
# 抛异常。历史上这两个返回值都被丢掉了,导致 5Hz LM 从未真正启动,而日志里
# 只有一行 llm_initialized=False,出歌照常"成功"。

class _FakeDit:
    def __init__(self, ok: bool, log: dict):
        self.ok = ok
        self.log = log

    def initialize_service(self, **kwargs):
        self.log["dit"] = kwargs
        return ("dit 初始化失败", self.ok)


class _FakeLLM:
    def __init__(self, ok: bool, log: dict):
        self.ok = ok
        self.log = log

    def initialize(self, **kwargs):
        self.log["lm"] = kwargs
        return ("lm 初始化失败", self.ok)


@pytest.fixture
def fake_acestep(monkeypatch):
    """把 acestep 的 handler 模块换成假的,避免测试里加载真模型。"""
    log: dict = {}

    def install(*, dit_ok=True, lm_ok=True):
        pkg = types.ModuleType("acestep")
        handler_mod = types.ModuleType("acestep.handler")
        handler_mod.AceStepHandler = lambda: _FakeDit(dit_ok, log)
        llm_mod = types.ModuleType("acestep.llm_inference")
        llm_mod.LLMHandler = lambda: _FakeLLM(lm_ok, log)
        monkeypatch.setitem(sys.modules, "acestep", pkg)
        monkeypatch.setitem(sys.modules, "acestep.handler", handler_mod)
        monkeypatch.setitem(sys.modules, "acestep.llm_inference", llm_mod)

    monkeypatch.setattr(song_gen, "_dit_handler", None)
    monkeypatch.setattr(song_gen, "_llm_handler", None)
    install.log = log
    return install


def test_dit_init_failure_raises(fake_acestep):
    fake_acestep(dit_ok=False)
    with pytest.raises(RuntimeError, match="dit 初始化失败"):
        song_gen._get_handlers()


def test_lm_init_failure_raises(fake_acestep):
    fake_acestep(lm_ok=False)
    with pytest.raises(RuntimeError, match="lm 初始化失败"):
        song_gen._get_handlers()


def test_failed_init_is_not_cached(fake_acestep):
    """初始化失败后不能把坏 handler 写进全局,否则之后每次调用都复用坏的。"""
    fake_acestep(lm_ok=False)
    with pytest.raises(RuntimeError):
        song_gen._get_handlers()

    fake_acestep(lm_ok=True)
    dit, llm = song_gen._get_handlers()
    assert dit is not None and llm is not None


def test_handlers_get_offload_from_config(fake_acestep, monkeypatch):
    """offload 由 config.acestep_offload 决定,不再写死 device == "cuda" ——
    那等于在 Mac 上永远关闭 offload,而 16GB 统一内存装不下两个模型。"""
    import config

    monkeypatch.setattr(config, "get_device", lambda: "mps")
    monkeypatch.setattr(config, "acestep_offload", lambda device: True)
    fake_acestep()
    song_gen._get_handlers()

    assert fake_acestep.log["dit"]["offload_to_cpu"] is True
    assert fake_acestep.log["lm"]["offload_to_cpu"] is True
