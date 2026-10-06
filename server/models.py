from pydantic import BaseModel, Field, field_validator

from src.presets import get_preset
from src.style_sampler import CREATIVITY_LEVELS
from src.textcheck import has_cjk
from src.vocal_timbres import get_timbre


class Overrides(BaseModel):
    genre: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    vocal_gender: str = ""
    language: str = ""
    # 风格预设 id;空 → generic。只由 UI 选择,planner 不自动推断。
    preset: str = ""
    # 人声音色 id;空 → 由采样器按曲风挑
    vocal_timbre: str = ""
    # 创意度:pure 纯正 / normal 常规 / fusion 融合
    creativity: str = "normal"

    @field_validator("vocal_timbre")
    @classmethod
    def _known_timbre(cls, v: str) -> str:
        get_timbre(v)  # 未知 id 抛 ValueError → 422
        return v

    @field_validator("creativity")
    @classmethod
    def _known_creativity(cls, v: str) -> str:
        if v not in CREATIVITY_LEVELS:
            raise ValueError(f"creativity must be one of {CREATIVITY_LEVELS}")
        return v


    @field_validator("genre", "mood")
    @classmethod
    def _english_tags_only(cls, v: list[str]) -> list[str]:
        # 前端显示中文、发送英文;中文混进 caption 会削弱 ACE-Step 的条件控制。
        if any(has_cjk(x) for x in v):
            raise ValueError("genre/mood must be English tags")
        return v

    @field_validator("preset")
    @classmethod
    def _known_preset(cls, v: str) -> str:
        get_preset(v)  # 未知 id 抛 ValueError → FastAPI 422
        return v


TITLE_MAX = 20


class GenerateRequest(BaseModel):
    lyrics: str
    # 用户自定义歌名;空 → 由 feeling/lyrics 自动命名。只是标签,不进 LLM/模型。
    title: str = ""
    feeling: str = ""
    length: str = "auto"      # auto(按歌词估算) | full | short(后两者只留给内部/测试用)
    seed: int | None = None
    instrumental: bool = False
    overrides: Overrides = Field(default_factory=Overrides)

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v: str) -> str:
        return v.strip()[:TITLE_MAX]

    @field_validator("length")
    @classmethod
    def _known_length(cls, v: str) -> str:
        if v not in ("auto", "full", "short"):
            raise ValueError("length must be auto/full/short")
        return v


class SongRename(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v: str) -> str:
        v = v.strip()[:TITLE_MAX]
        if not v:
            raise ValueError("title must not be blank")
        return v


CATEGORY_NAME_MAX = 20


class CategoryCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        v = v.strip()[:CATEGORY_NAME_MAX]
        if not v:
            raise ValueError("name must not be blank")
        return v
