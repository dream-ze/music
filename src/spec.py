from pydantic import BaseModel, Field, ValidationError, field_validator

from src.textcheck import has_cjk

# ACE-Step VALID_LANGUAGES 中本项目支持的子集(其余一律归一为 unknown)
VALID_LANGUAGES = {"zh", "en", "yue", "unknown"}
_VALID_TIMESIGNATURES = {2, 3, 4, 6}


class VocalSpec(BaseModel):
    gender: str = "female"
    style: str = "soft"


class SongSpec(BaseModel):
    language: str = "zh"
    vocal: VocalSpec = Field(default_factory=VocalSpec)
    genre: list[str] = Field(default_factory=lambda: ["mandopop"])
    mood: list[str] = Field(default_factory=lambda: ["warm"])
    instrument: list[str] = Field(default_factory=lambda: ["piano", "soft drums"])
    bpm: int = Field(default=90, ge=40, le=200)
    structure: list[str] = Field(
        default_factory=lambda: ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"]
    )
    # ── 2026-09 输入链重建新增(均有默认值,兼容旧 spec_json) ──
    caption: str = ""            # 英文整句;空表示回退到标签串
    caption_full: bool = False   # caption 是否为 planner 产出的完整整句 → 决定 use_cot_caption
    keyscale: str = ""           # 如 "F minor";空交给 LM
    timesignature: int | None = None
    preset_id: str = "generic"

    @field_validator("caption", "genre", "mood", "instrument")
    @classmethod
    def _no_cjk(cls, v):
        items = v if isinstance(v, list) else [v]
        if any(has_cjk(x) for x in items):
            raise ValueError("must not contain CJK characters")
        return v

    @field_validator("caption")
    @classmethod
    def _caption_len(cls, v: str) -> str:
        if len(v) > 512:
            raise ValueError("caption longer than 512 chars")
        return v

    @field_validator("language")
    @classmethod
    def _language(cls, v: str) -> str:
        if v not in VALID_LANGUAGES:
            raise ValueError(f"language must be one of {sorted(VALID_LANGUAGES)}")
        return v

    @field_validator("timesignature")
    @classmethod
    def _timesig(cls, v):
        if v is not None and v not in _VALID_TIMESIGNATURES:
            raise ValueError("timesignature must be 2/3/4/6")
        return v


SAFE_DEFAULT_SPEC: dict = {
    "language": "zh",
    "vocal": {"gender": "female", "style": "soft"},
    "genre": ["mandopop"],
    "mood": ["warm"],
    "instrument": ["piano", "soft drums"],
    "bpm": 90,
    "structure": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
}


def parse_spec(data: dict) -> SongSpec:
    try:
        return SongSpec(**data)
    except ValidationError as e:
        raise ValueError(str(e)) from e


def safe_spec() -> SongSpec:
    """测试与兼容用的通用 spec。planner 降级不再用它,而是用 preset 骨架。"""
    return SongSpec(**SAFE_DEFAULT_SPEC)
