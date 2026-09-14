"""风格 Preset 层:每个 preset 是一份数据,不是代码分支。新增风格只加一条数据。"""
from pydantic import BaseModel, Field


class LyricRules(BaseModel):
    min_syllables: int = 6
    max_syllables: int = 10
    tolerance: int = 2


class AceStepKnobs(BaseModel):
    shift: float = 3.0
    # 混合语言(中英)时 vocal_language 取值;A/B 时可改 "unknown"
    vocal_language_policy: str = "zh"


class Preset(BaseModel):
    id: str
    label: str
    family: str
    # 英文整句模板,占位符 {instruments} {texture} {era} {vocal}
    caption_skeleton: str
    genre_tags: list[str] = Field(default_factory=list)
    instrument_pool: list[str] = Field(default_factory=list)
    texture_pool: list[str] = Field(default_factory=list)
    era_pool: list[str] = Field(default_factory=list)
    bpm_range: tuple[int, int] = (60, 160)
    keyscale_hint: str = ""
    timesignature: int = 4
    structure: list[str]
    vocal_qualifier: str = ""
    vocal_gender_default: str = "female"
    lyric_rules: LyricRules = Field(default_factory=LyricRules)
    acestep: AceStepKnobs = Field(default_factory=AceStepKnobs)
    # 官方句式示例,注入 planner 提示词
    examples: list[str] = Field(default_factory=list)

    def render_skeleton(self, vocal_gender: str | None = None) -> str:
        """planner 降级时用的英文 caption:池中前几项填充占位符。"""
        instruments = ", ".join(self.instrument_pool[:3]) or "drums, bass, keys"
        texture = ", ".join(self.texture_pool[:2]) or "clean, balanced"
        era = self.era_pool[0] if self.era_pool else "modern"
        vocal = f"{vocal_gender or self.vocal_gender_default} {self.vocal_qualifier or 'vocal'}"
        return self.caption_skeleton.format(
            instruments=instruments, texture=texture, era=era, vocal=vocal
        )

    def bpm_default(self) -> int:
        lo, hi = self.bpm_range
        return (lo + hi) // 2


_GENERIC = Preset(
    id="generic", label="自动", family="generic",
    caption_skeleton=(
        "A {era} track featuring {instruments}, with a {texture} production "
        "and a {vocal} carrying the melody."
    ),
    genre_tags=["pop"],
    bpm_range=(60, 160),
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
    examples=[
        "A warm, mid-tempo pop ballad led by soft piano and airy pads, with an "
        "intimate female vocal that builds into a layered, emotive chorus."
    ],
)

_BOOM_BAP = Preset(
    id="hiphop.boom_bap", label="Boom Bap", family="hiphop",
    caption_skeleton=(
        "A {era} boom bap hip-hop track built on {instruments}. The production feels "
        "{texture}, and a confident {vocal} rides the beat with a steady, articulate flow."
    ),
    genre_tags=["hip hop", "boom bap"],
    instrument_pool=["dusty drum break", "upright bass", "jazzy piano sample",
                     "vinyl crackle", "muted trumpet stabs"],
    texture_pool=["warm", "gritty", "lo-fi"],
    era_pool=["90s", "golden era"],
    bpm_range=(85, 95),
    keyscale_hint="minor",
    structure=["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    vocal_qualifier="rap",
    vocal_gender_default="male",
    examples=[
        "A catchy Chinese hip-hop track with confident male rap verses, boom bap drums, "
        "and a melodic sung hook. The production features a dusty drum break, upright "
        "bass, jazzy piano samples and vinyl crackle, with a warm, gritty 90s feel.",
    ],
)

_TRAP = Preset(
    id="hiphop.trap", label="Trap", family="hiphop",
    caption_skeleton=(
        "A {era} trap track driven by {instruments}. The mix is {texture}, and an "
        "assertive {vocal} delivers tight verses over the beat with a melodic hook."
    ),
    genre_tags=["hip hop", "trap"],
    instrument_pool=["808 sub-bass", "rolling hi-hats", "trap drums",
                     "dark synth pads", "vocal chops"],
    texture_pool=["punchy", "dark", "modern"],
    era_pool=["modern", "2020s"],
    bpm_range=(130, 150),
    keyscale_hint="minor",
    structure=["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    vocal_qualifier="rap",
    vocal_gender_default="male",
    examples=[
        "A Chinese trap song with aggressive male rap, heavy 808s, and dark atmospheric "
        "synths. The production features hard-hitting drums, rolling hi-hats, vocal "
        "chops, and an intense energy throughout.",
    ],
)

PRESETS: dict[str, Preset] = {p.id: p for p in (_GENERIC, _BOOM_BAP, _TRAP)}


def get_preset(preset_id: str | None) -> Preset:
    """空 id → generic;未知 id 抛 ValueError(API 层转 422)。"""
    if not preset_id:
        return PRESETS["generic"]
    try:
        return PRESETS[preset_id]
    except KeyError as exc:
        raise ValueError(f"未知风格预设: {preset_id}") from exc
