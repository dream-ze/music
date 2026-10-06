"""风格 Preset 层:每个 preset 是一份数据,不是代码分支。新增风格只加一条数据。"""
from pydantic import BaseModel, Field, model_validator


class LyricRules(BaseModel):
    min_syllables: int = 6
    max_syllables: int = 10
    tolerance: int = 2


class AceStepKnobs(BaseModel):
    shift: float = 3.0
    # 混合语言(中英)时 vocal_language 取值;A/B 时可改 "unknown"
    vocal_language_policy: str = "zh"


# 编曲角色,采样时按此顺序逐池抽取。
# 角色分池 + 互斥规则的做法参考 ddv1982/suno-prompting(MIT)。
POOL_ORDER = ("harmonic", "color", "rhythm", "rare")


class Pool(BaseModel):
    """一个编曲角色的乐器池:每次抽 pick_min..pick_max 件;chance<1 表示整池按概率参与(rare 用)。"""
    items: list[str]
    pick_min: int = 1
    pick_max: int = 1
    chance: float = 1.0

    @model_validator(mode="after")
    def _check(self):
        if not 0 <= self.pick_min <= self.pick_max <= len(self.items):
            raise ValueError("need 0 <= pick_min <= pick_max <= len(items)")
        if not 0 < self.chance <= 1:
            raise ValueError("chance must be in (0, 1]")
        return self


class Preset(BaseModel):
    id: str
    label: str
    family: str
    # 英文整句模板,占位符 {instruments} {texture} {era} {vocal}
    caption_skeleton: str
    genre_tags: list[str] = Field(default_factory=list)
    # 曲风识别用(中英皆可,小写子串匹配)
    keywords: list[str] = Field(default_factory=list)
    # caption 校验:至少命中一个(英文,小写);空 = 不校验曲风词
    caption_keywords: list[str] = Field(default_factory=list)
    # 冲突词:caption 命中即不合格
    avoid: list[str] = Field(default_factory=list)
    instrument_pools: dict[str, Pool] = Field(default_factory=dict)
    exclusions: list[tuple[str, str]] = Field(default_factory=list)
    texture_pool: list[str] = Field(default_factory=list)
    era_pool: list[str] = Field(default_factory=list)
    mood_pool: list[str] = Field(default_factory=list)
    bpm_range: tuple[int, int] = (60, 160)
    bpm_typical: int | None = None
    keyscale_hint: str = ""
    timesignature: int = 4
    structure: list[str]
    vocal_qualifier: str = ""
    vocal_gender_default: str = "female"
    # 本曲风适合的人声音色 id(见 src/vocal_timbres.py),未锁定时从中采样
    vocal_timbres: list[str] = Field(default_factory=list)
    # 融合档可选的伙伴曲风 id(人工挑选的兼容对)
    fusion_partners: list[str] = Field(default_factory=list)
    lyric_rules: LyricRules = Field(default_factory=LyricRules)
    acestep: AceStepKnobs = Field(default_factory=AceStepKnobs)
    # 兜底示例:示例库检索不到时才注入 planner
    examples: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self):
        unknown = set(self.instrument_pools) - set(POOL_ORDER)
        if unknown:
            raise ValueError(f"unknown pool roles: {sorted(unknown)}")
        items = set(self.instrument_pool)
        for a, b in self.exclusions:
            if a not in items or b not in items:
                raise ValueError(f"exclusion ({a}, {b}) references an item not in pools")
        lo, hi = self.bpm_range
        if self.bpm_typical is not None and not lo <= self.bpm_typical <= hi:
            raise ValueError("bpm_typical out of bpm_range")
        return self

    @property
    def instrument_pool(self) -> list[str]:
        """所有角色池按 POOL_ORDER 展平(planner 提示词与旧调用方用)。"""
        out: list[str] = []
        for role in POOL_ORDER:
            pool = self.instrument_pools.get(role)
            if pool:
                out.extend(pool.items)
        return out

    def render_skeleton(self, vocal_gender: str | None = None, *,
                        instruments: list[str] | None = None,
                        textures: list[str] | None = None,
                        era: str | None = None,
                        vocal: str | None = None) -> str:
        """planner 降级时用的英文 caption。传了采样结果就用采样结果,否则每个必选池取第一项。"""
        if instruments is None:
            instruments = [p.items[0] for r in POOL_ORDER
                           if (p := self.instrument_pools.get(r)) and p.pick_min > 0][:3]
        if textures is None:
            textures = self.texture_pool[:2]
        era = era or (self.era_pool[0] if self.era_pool else "modern")
        vocal = vocal or f"{vocal_gender or self.vocal_gender_default} {self.vocal_qualifier or 'vocal'}"
        return self.caption_skeleton.format(
            instruments=", ".join(instruments) or "drums, bass, keys",
            texture=", ".join(textures) or "clean, balanced",
            era=era, vocal=vocal,
        )

    def bpm_default(self) -> int:
        if self.bpm_typical is not None:
            return self.bpm_typical
        lo, hi = self.bpm_range
        return (lo + hi) // 2


_GENERIC = Preset(
    id="generic", label="自动", family="generic",
    caption_skeleton=(
        "A {era} track featuring {instruments}, with a {texture} production "
        "and a {vocal} carrying the melody."
    ),
    genre_tags=["pop"],
    mood_pool=["warm", "hopeful", "nostalgic"],
    bpm_range=(60, 160),
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
    vocal_timbres=["clear", "breathy", "deep", "powerful"],
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
    keywords=["boom bap", "老派", "old school", "说唱", "嘻哈", "hip hop", "hiphop", "rap"],
    caption_keywords=["boom bap"],
    avoid=["supersaw", "festival", "banjo"],
    instrument_pools={
        "harmonic": Pool(items=["jazzy piano sample", "Rhodes sample", "soul guitar loop"]),
        "color": Pool(items=["muted trumpet stabs", "vinyl crackle", "soul vocal sample"],
                      pick_max=2),
        "rhythm": Pool(items=["dusty drum break", "upright bass"], pick_min=2, pick_max=2),
        "rare": Pool(items=["turntable scratches"], pick_min=0, pick_max=1, chance=0.3),
    },
    texture_pool=["warm", "gritty", "lo-fi", "dusty"],
    era_pool=["90s", "golden era"],
    mood_pool=["confident", "nocturnal", "introspective", "nostalgic", "gritty"],
    bpm_range=(85, 95), bpm_typical=90,
    keyscale_hint="minor",
    structure=["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    vocal_qualifier="rap",
    vocal_gender_default="male",
    vocal_timbres=["rap_laidback", "rap_rapid", "deep", "raspy"],
    fusion_partners=["jazz.lounge", "lofi.chill"],
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
    keywords=["trap", "808", "drill", "陷阱"],
    caption_keywords=["trap"],
    avoid=["banjo", "acoustic ballad", "jazz trio"],
    instrument_pools={
        "harmonic": Pool(items=["dark synth pads", "eerie piano melody", "bell melody"]),
        "color": Pool(items=["vocal chops", "plucked synth", "choir pad"], pick_min=0),
        "rhythm": Pool(items=["808 sub-bass", "rolling hi-hats", "hard-hitting trap drums"],
                       pick_min=2, pick_max=3),
        "rare": Pool(items=["flute loop"], pick_min=0, pick_max=1, chance=0.25),
    },
    texture_pool=["punchy", "dark", "modern", "hard-hitting"],
    era_pool=["modern", "2020s"],
    mood_pool=["dark", "aggressive", "confident", "menacing", "hypnotic"],
    bpm_range=(130, 150), bpm_typical=140,
    keyscale_hint="minor",
    structure=["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    vocal_qualifier="rap",
    vocal_gender_default="male",
    vocal_timbres=["rap_rapid", "rap_laidback", "raspy", "deep"],
    fusion_partners=["electronic.dance", "rnb.soul"],
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
