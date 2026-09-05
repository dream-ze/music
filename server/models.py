from pydantic import BaseModel, Field


class Overrides(BaseModel):
    genre: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    vocal_gender: str = ""
    language: str = ""


class GenerateRequest(BaseModel):
    lyrics: str
    feeling: str = ""
    length: str = "full"      # full | short
    seed: int | None = None
    instrumental: bool = False
    overrides: Overrides = Field(default_factory=Overrides)
