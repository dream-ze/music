from pydantic import BaseModel, Field, field_validator

from src.presets import get_preset
from src.textcheck import has_cjk


class Overrides(BaseModel):
    genre: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    vocal_gender: str = ""
    language: str = ""
    # 风格预设 id;空 → generic。只由 UI 选择,planner 不自动推断。
    preset: str = ""

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


class GenerateRequest(BaseModel):
    lyrics: str
    feeling: str = ""
    length: str = "full"      # full | short
    seed: int | None = None
    instrumental: bool = False
    overrides: Overrides = Field(default_factory=Overrides)
