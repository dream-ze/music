from pydantic import BaseModel, Field, ValidationError


class VocalSpec(BaseModel):
    gender: str = "female"
    style: str = "soft"


class SongSpec(BaseModel):
    language: str = "zh"
    vocal: VocalSpec = Field(default_factory=VocalSpec)
    genre: list[str] = Field(default_factory=lambda: ["mandopop"])
    mood: list[str] = Field(default_factory=lambda: ["warm"])
    instrument: list[str] = Field(default_factory=lambda: ["piano"])
    bpm: int = Field(default=90, ge=40, le=200)
    structure: list[str] = Field(
        default_factory=lambda: ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"]
    )


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
    return SongSpec(**SAFE_DEFAULT_SPEC)
