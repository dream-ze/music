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


_BALLAD = Preset(
    id="pop.ballad", label="流行抒情", family="pop",
    caption_skeleton=(
        "A {era} pop ballad featuring {instruments}, with a {texture} production and a "
        "{vocal} carrying an emotional melody that swells into the chorus."
    ),
    genre_tags=["pop", "ballad"],
    keywords=["抒情", "情歌", "慢歌", "流行", "ballad", "pop"],
    caption_keywords=["ballad"],
    avoid=["808", "trap", "distorted guitar", "dubstep"],
    instrument_pools={
        "harmonic": Pool(items=["grand piano", "felt piano", "electric piano"]),
        "color": Pool(items=["string section", "cello", "acoustic guitar", "airy synth pads",
                             "soft choir"], pick_max=2),
        "rhythm": Pool(items=["soft drums", "brushed drums", "electric bass"]),
        "rare": Pool(items=["music box", "glockenspiel"], pick_min=0, pick_max=1, chance=0.2),
    },
    texture_pool=["warm", "lush", "polished", "intimate"],
    era_pool=["modern", "2010s", "2000s"],
    mood_pool=["tender", "bittersweet", "nostalgic", "hopeful", "melancholic"],
    bpm_range=(60, 84), bpm_typical=72,
    structure=["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Chorus", "Bridge",
               "Chorus", "Outro"],
    vocal_timbres=["clear", "breathy", "powerful", "falsetto", "soft_whisper"],
    fusion_partners=["rnb.soul", "folk.acoustic"],
    examples=[
        "An emotional pop ballad that opens with gentle felt piano and a breathy female "
        "vocal, then swells with a string section and soft drums into a soaring, "
        "heartfelt chorus.",
    ],
)

_CITY_POP = Preset(
    id="pop.city_pop", label="City Pop", family="pop",
    caption_skeleton=(
        "A {era} city pop track with {instruments}. The production is {texture}, and a "
        "{vocal} glides over a groovy, nostalgic beat."
    ),
    genre_tags=["city pop", "pop"],
    keywords=["city pop", "citypop", "城市流行", "都市", "日系", "复古流行"],
    caption_keywords=["city pop"],
    avoid=["808", "trap", "metal", "distorted"],
    instrument_pools={
        "harmonic": Pool(items=["Rhodes electric piano", "bright synth keys",
                                "clean electric guitar chords"]),
        "color": Pool(items=["funky slap bass", "brass section", "saxophone solo",
                             "lush strings"], pick_max=2),
        "rhythm": Pool(items=["groovy live drums", "four-on-the-floor drums"]),
        "rare": Pool(items=["vibraphone", "synth arpeggio"], pick_min=0, pick_max=1,
                     chance=0.3),
    },
    texture_pool=["glossy", "bright", "polished", "retro"],
    era_pool=["80s", "late 80s Japanese", "80s Tokyo"],
    mood_pool=["nostalgic", "breezy", "romantic", "dreamy", "carefree"],
    bpm_range=(96, 120), bpm_typical=108,
    structure=["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Chorus", "Outro"],
    vocal_timbres=["clear", "breathy", "soft_whisper", "falsetto"],
    fusion_partners=["jazz.lounge", "electronic.synthwave"],
    examples=[
        "A breezy 80s city pop song with a glossy Rhodes electric piano, funky slap bass "
        "and a brass section over groovy live drums, sung by a clear, airy female vocal "
        "with a nostalgic, romantic mood.",
    ],
)

_FOLK = Preset(
    id="folk.acoustic", label="民谣", family="folk",
    caption_skeleton=(
        "A {era} acoustic folk song built on {instruments}, with a {texture} recording "
        "and a {vocal} telling the story."
    ),
    genre_tags=["folk", "acoustic"],
    keywords=["民谣", "木吉他", "吉他弹唱", "folk", "acoustic"],
    caption_keywords=["folk"],
    avoid=["808", "synth bass", "edm", "trap", "distorted"],
    instrument_pools={
        "harmonic": Pool(items=["fingerpicked acoustic guitar", "strummed acoustic guitar",
                                "nylon-string guitar"]),
        "color": Pool(items=["harmonica", "cello", "violin", "mandolin", "soft piano",
                             "banjo"], pick_max=2),
        "rhythm": Pool(items=["light percussion", "upright bass", "cajon"], pick_min=0),
        "rare": Pool(items=["accordion", "glockenspiel"], pick_min=0, pick_max=1, chance=0.2),
    },
    exclusions=[("mandolin", "banjo")],
    texture_pool=["warm", "organic", "intimate", "raw"],
    era_pool=["modern", "70s", "2010s indie"],
    mood_pool=["nostalgic", "tender", "wistful", "peaceful", "heartfelt"],
    bpm_range=(70, 110), bpm_typical=90,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
    vocal_gender_default="male",
    vocal_timbres=["clear", "breathy", "raspy", "deep", "soft_whisper"],
    fusion_partners=["pop.ballad", "cn.guofeng"],
    examples=[
        "A warm acoustic folk song with fingerpicked guitar, harmonica and a touch of "
        "cello, recorded with an intimate, organic feel and a gentle male vocal that "
        "tells a nostalgic story.",
    ],
)

_ROCK = Preset(
    id="rock.band", label="摇滚", family="rock",
    caption_skeleton=(
        "A {era} rock track driven by {instruments}. The mix is {texture}, and a "
        "{vocal} pushes through anthemic choruses."
    ),
    genre_tags=["rock"],
    keywords=["摇滚", "乐队", "硬摇", "rock", "band"],
    caption_keywords=["rock"],
    avoid=["808", "trap", "lo-fi"],
    instrument_pools={
        "harmonic": Pool(items=["distorted electric guitar", "crunchy rhythm guitar",
                                "overdriven guitar riffs"]),
        "color": Pool(items=["lead guitar solo", "Hammond organ", "piano stabs",
                             "string pads"]),
        "rhythm": Pool(items=["punchy live drums", "driving bass guitar"], pick_min=2,
                       pick_max=2),
        "rare": Pool(items=["tambourine", "cowbell"], pick_min=0, pick_max=1, chance=0.25),
    },
    texture_pool=["raw", "punchy", "gritty", "arena-sized"],
    era_pool=["90s", "2000s", "modern", "70s classic"],
    mood_pool=["defiant", "energetic", "triumphant", "rebellious", "anthemic"],
    bpm_range=(100, 140), bpm_typical=120,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
    vocal_gender_default="male",
    vocal_timbres=["raspy", "powerful", "clear", "theatrical"],
    fusion_partners=["rock.pop_punk", "rock.anime"],
    examples=[
        "An energetic rock anthem driven by crunchy distorted guitars, punchy live drums "
        "and a driving bass line, with a raspy, powerful male vocal and a lead guitar "
        "solo before the final chorus.",
    ],
)

_POP_PUNK = Preset(
    id="rock.pop_punk", label="流行朋克", family="rock",
    caption_skeleton=(
        "A {era} pop punk anthem with {instruments}. It sounds {texture}, with a "
        "{vocal} shouting a catchy, sing-along chorus."
    ),
    genre_tags=["pop punk", "punk"],
    keywords=["流行朋克", "朋克", "pop punk", "punk"],
    caption_keywords=["punk"],
    avoid=["808", "ballad", "jazz", "orchestral"],
    instrument_pools={
        "harmonic": Pool(items=["fast power chords", "palm-muted guitars",
                                "bright distorted guitars"]),
        "color": Pool(items=["lead guitar hooks", "synth leads", "gang vocal shouts"],
                      pick_min=0),
        "rhythm": Pool(items=["fast punk drums", "driving bass guitar"], pick_min=2,
                       pick_max=2),
        "rare": Pool(items=["handclaps"], pick_min=0, pick_max=1, chance=0.3),
    },
    texture_pool=["energetic", "raw", "bright", "youthful"],
    era_pool=["2000s", "modern", "early 2000s"],
    mood_pool=["rebellious", "carefree", "youthful", "energetic", "bittersweet"],
    bpm_range=(150, 185), bpm_typical=165,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
    vocal_gender_default="male",
    vocal_timbres=["raspy", "powerful", "clear"],
    fusion_partners=["rock.band", "electronic.dance"],
    examples=[
        "A fast, youthful pop punk song with bright distorted power chords, energetic "
        "punk drums and a catchy shouted chorus from a raspy male vocal, full of "
        "carefree, rebellious energy.",
    ],
)

_RNB = Preset(
    id="rnb.soul", label="R&B / Soul", family="rnb",
    caption_skeleton=(
        "A {era} R&B soul track with {instruments}. The production is {texture}, and a "
        "{vocal} delivers smooth, soulful runs."
    ),
    genre_tags=["r&b", "soul"],
    keywords=["节奏布鲁斯", "灵魂乐", "律动", "r&b", "rnb", "soul"],
    caption_keywords=["r&b", "soul", "rnb"],
    avoid=["distorted", "metal", "punk", "banjo"],
    instrument_pools={
        "harmonic": Pool(items=["Rhodes electric piano", "warm keys",
                                "neo-soul guitar chords"]),
        "color": Pool(items=["lush strings", "muted horns", "layered backing vocals",
                             "synth bass"], pick_max=2),
        "rhythm": Pool(items=["laid-back drums", "smooth bass line", "finger snaps"],
                       pick_max=2),
        "rare": Pool(items=["vibraphone", "harp"], pick_min=0, pick_max=1, chance=0.2),
    },
    exclusions=[("synth bass", "smooth bass line")],
    texture_pool=["smooth", "silky", "warm", "intimate"],
    era_pool=["90s", "modern", "2000s", "70s"],
    mood_pool=["sensual", "late-night", "soulful", "romantic", "yearning"],
    bpm_range=(70, 100), bpm_typical=85,
    structure=["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Chorus", "Bridge",
               "Chorus", "Outro"],
    vocal_timbres=["breathy", "falsetto", "deep", "powerful", "soft_whisper"],
    fusion_partners=["pop.ballad", "hiphop.boom_bap"],
    examples=[
        "A smooth late-night R&B song with warm Rhodes chords, laid-back drums and a "
        "deep bass line, featuring a silky female vocal with soulful runs and layered "
        "backing harmonies.",
    ],
)

_DANCE = Preset(
    id="electronic.dance", label="电子舞曲", family="electronic",
    caption_skeleton=(
        "A {era} electronic dance track built on {instruments}. The mix is {texture}, "
        "with a {vocal} over a euphoric build and drop."
    ),
    genre_tags=["edm", "dance", "electronic"],
    keywords=["电子舞曲", "舞曲", "蹦迪", "edm", "dance", "house", "club"],
    caption_keywords=["dance", "edm", "house"],
    avoid=["acoustic ballad", "banjo", "jazz trio", "upright bass"],
    instrument_pools={
        "harmonic": Pool(items=["supersaw synth chords", "plucky synth lead",
                                "bright synth stabs"]),
        "color": Pool(items=["vocal chops", "risers and sweeps", "arpeggiated synths",
                             "piano house chords"], pick_max=2),
        "rhythm": Pool(items=["four-on-the-floor kick", "sidechained bass", "crisp claps"],
                       pick_min=2, pick_max=2),
        "rare": Pool(items=["acid synth line", "talk box"], pick_min=0, pick_max=1,
                     chance=0.25),
    },
    texture_pool=["euphoric", "punchy", "polished", "festival-sized"],
    era_pool=["modern", "2010s", "2020s"],
    mood_pool=["euphoric", "energetic", "uplifting", "hypnotic", "dreamy"],
    bpm_range=(118, 130), bpm_typical=124,
    structure=["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Chorus", "Outro"],
    vocal_timbres=["clear", "powerful", "breathy", "falsetto"],
    fusion_partners=["electronic.synthwave", "pop.city_pop"],
    examples=[
        "An uplifting electronic dance track with a four-on-the-floor kick, sidechained "
        "bass and bright supersaw chords, building through risers into a euphoric drop "
        "with a clear, powerful female vocal.",
    ],
)

_LOFI = Preset(
    id="lofi.chill", label="Lo-fi", family="chill",
    caption_skeleton=(
        "A {era} lo-fi chill track with {instruments}. The sound is {texture}, and a "
        "{vocal} hums over a relaxed, dusty groove."
    ),
    genre_tags=["lo-fi", "chill"],
    keywords=["低保真", "学习", "放松", "咖啡", "lofi", "lo-fi", "chill"],
    caption_keywords=["lo-fi", "lofi"],
    avoid=["distorted", "metal", "festival", "supersaw"],
    instrument_pools={
        "harmonic": Pool(items=["mellow electric piano", "jazzy guitar chords", "soft piano"]),
        "color": Pool(items=["vinyl crackle", "tape hiss", "warm synth pads", "muted trumpet"],
                      pick_max=2),
        "rhythm": Pool(items=["dusty boom bap drums", "soft kick and snare", "round bass"],
                       pick_max=2),
        "rare": Pool(items=["rain ambience", "wind chimes"], pick_min=0, pick_max=1,
                     chance=0.3),
    },
    exclusions=[("dusty boom bap drums", "soft kick and snare")],
    texture_pool=["warm", "hazy", "lo-fi", "mellow"],
    era_pool=["modern", "90s-inspired", "bedroom"],
    mood_pool=["relaxed", "nostalgic", "cozy", "dreamy", "melancholic"],
    bpm_range=(70, 90), bpm_typical=80,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
    vocal_timbres=["soft_whisper", "breathy", "deep", "rap_laidback"],
    fusion_partners=["jazz.lounge", "hiphop.boom_bap"],
    examples=[
        "A cozy lo-fi chill track with mellow electric piano, vinyl crackle and dusty "
        "drums, with a soft, hushed female vocal drifting over a warm, hazy groove.",
    ],
)

# 乐器池与互斥规则改编自 ddv1982/suno-prompting 的 jazz 定义(MIT License)
_JAZZ = Preset(
    id="jazz.lounge", label="爵士", family="chill",
    caption_skeleton=(
        "A {era} jazz song with {instruments}. The recording feels {texture}, and a "
        "{vocal} sings with a swinging, late-night elegance."
    ),
    genre_tags=["jazz"],
    keywords=["爵士", "摇摆", "酒吧", "jazz", "swing", "bossa"],
    caption_keywords=["jazz", "swing", "bossa nova"],
    avoid=["808", "edm", "distorted", "trap"],
    instrument_pools={
        "harmonic": Pool(items=["Rhodes", "grand piano", "hollowbody guitar",
                                "Hammond organ"]),
        "color": Pool(items=["tenor sax", "alto sax", "muted trumpet", "flugelhorn",
                             "trombone", "vibraphone", "clarinet"], pick_max=2),
        "rhythm": Pool(items=["upright bass", "walking bass", "brushed drums", "ride cymbal"],
                       pick_max=2),
        "rare": Pool(items=["congas", "bongos"], pick_min=0, pick_max=1, chance=0.2),
    },
    exclusions=[("tenor sax", "alto sax"), ("muted trumpet", "flugelhorn"),
                ("upright bass", "walking bass"), ("congas", "bongos")],
    texture_pool=["smooth", "warm", "intimate", "live"],
    era_pool=["50s", "60s", "modern"],
    mood_pool=["smooth", "sophisticated", "late-night", "laid-back", "romantic"],
    bpm_range=(80, 160), bpm_typical=110,
    structure=["Intro", "Verse", "Chorus", "Instrumental", "Verse", "Chorus", "Outro"],
    vocal_timbres=["deep", "breathy", "soft_whisper", "clear"],
    fusion_partners=["rnb.soul", "lofi.chill"],
    examples=[
        "A smooth late-night jazz song with brushed drums, walking upright bass and a "
        "grand piano, a muted trumpet answering a warm, breathy female vocal in an "
        "intimate live-room recording.",
    ],
)

_GUOFENG = Preset(
    id="cn.guofeng", label="中国风", family="cn",
    caption_skeleton=(
        "A {era} Chinese-style pop song blending {instruments}. The production is "
        "{texture}, and a {vocal} sings a graceful, pentatonic melody."
    ),
    genre_tags=["chinese traditional", "c-pop"],
    keywords=["中国风", "古风", "国风", "戏腔", "古筝", "chinese style", "guofeng"],
    caption_keywords=["chinese-style", "chinese style", "guzheng", "erhu", "pipa",
                      "pentatonic"],
    avoid=["banjo", "country", "metal"],
    instrument_pools={
        "harmonic": Pool(items=["guzheng", "pipa", "soft piano"]),
        "color": Pool(items=["erhu", "dizi bamboo flute", "xiao flute", "guqin",
                             "string section"], pick_max=2),
        "rhythm": Pool(items=["soft drums", "traditional percussion", "deep bass"]),
        "rare": Pool(items=["temple bells", "chinese gong"], pick_min=0, pick_max=1,
                     chance=0.25),
    },
    exclusions=[("dizi bamboo flute", "xiao flute")],
    texture_pool=["elegant", "cinematic", "ethereal", "lush"],
    era_pool=["modern", "ancient-inspired"],
    mood_pool=["poetic", "melancholic", "graceful", "nostalgic", "epic"],
    bpm_range=(66, 96), bpm_typical=80,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
    vocal_timbres=["clear", "breathy", "theatrical", "falsetto"],
    fusion_partners=["pop.ballad", "electronic.dance"],
    examples=[
        "An elegant Chinese-style pop song that opens with guzheng and dizi bamboo flute, "
        "adds an erhu line and soft drums, and features a clear, graceful female vocal "
        "singing a poetic pentatonic melody.",
    ],
)

_ANIME = Preset(
    id="rock.anime", label="动漫 / J-Rock", family="rock",
    caption_skeleton=(
        "A {era} anime-style J-rock song with {instruments}. The mix is {texture}, and a "
        "{vocal} soars through a dramatic, high-energy chorus."
    ),
    genre_tags=["j-rock", "anime"],
    keywords=["动漫", "动画", "番剧", "日系摇滚", "热血", "anime", "j-rock"],
    caption_keywords=["anime", "j-rock"],
    avoid=["808", "lo-fi", "country", "jazz trio"],
    instrument_pools={
        "harmonic": Pool(items=["fast distorted guitars", "bright overdriven guitar riffs"]),
        "color": Pool(items=["synth brass fanfare", "piano runs", "string section",
                             "lead guitar solo"], pick_max=2),
        "rhythm": Pool(items=["driving rock drums", "busy bass guitar"], pick_min=2,
                       pick_max=2),
        "rare": Pool(items=["synth arpeggios", "glockenspiel"], pick_min=0, pick_max=1,
                     chance=0.3),
    },
    texture_pool=["bright", "dense", "punchy", "dramatic"],
    era_pool=["2010s", "modern", "2000s"],
    mood_pool=["triumphant", "adventurous", "passionate", "exhilarating", "bittersweet"],
    bpm_range=(135, 185), bpm_typical=150,
    structure=["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Chorus", "Bridge",
               "Chorus", "Outro"],
    vocal_gender_default="male",
    vocal_timbres=["powerful", "clear", "theatrical", "raspy"],
    fusion_partners=["rock.band", "electronic.dance"],
    examples=[
        "An explosive anime-style J-rock song with fast distorted guitars, a synth brass "
        "fanfare and driving drums, led by a powerful, theatrical male vocal that soars "
        "into a triumphant chorus.",
    ],
)

_SYNTHWAVE = Preset(
    id="electronic.synthwave", label="Synthwave", family="electronic",
    caption_skeleton=(
        "A {era} synthwave track with {instruments}. The sound is {texture}, and a "
        "{vocal} floats over neon-lit, retro-futuristic grooves."
    ),
    genre_tags=["synthwave", "retro"],
    keywords=["合成器", "复古电子", "赛博", "霓虹", "80年代", "synthwave", "retrowave"],
    caption_keywords=["synthwave", "retrowave"],
    avoid=["banjo", "upright bass", "trap", "acoustic ballad"],
    instrument_pools={
        "harmonic": Pool(items=["analog synth pads", "warm polysynth chords"]),
        "color": Pool(items=["bright synth lead", "electric guitar solo", "saxophone",
                             "arpeggiated synth bass"], pick_max=2),
        "rhythm": Pool(items=["gated reverb drums", "linn drum machine", "pulsing bass"],
                       pick_max=2),
        "rare": Pool(items=["vocoder", "talk box"], pick_min=0, pick_max=1, chance=0.25),
    },
    exclusions=[("gated reverb drums", "linn drum machine"),
                ("arpeggiated synth bass", "pulsing bass")],
    texture_pool=["neon", "shimmering", "nostalgic", "glossy"],
    era_pool=["80s", "retro 80s", "modern retro"],
    mood_pool=["nostalgic", "nocturnal", "dreamy", "driving", "melancholic"],
    bpm_range=(84, 118), bpm_typical=100,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
    vocal_gender_default="male",
    vocal_timbres=["clear", "breathy", "deep", "falsetto"],
    fusion_partners=["pop.city_pop", "rock.band"],
    examples=[
        "A nocturnal 80s synthwave track with shimmering analog synth pads, gated reverb "
        "drums and a pulsing bass, a bright synth lead and a deep male vocal drifting "
        "through a neon-lit, nostalgic atmosphere.",
    ],
)

# 前端展示顺序,也是随机挑曲风的候选集(generic 不在其中,只作最终兜底)
UI_GENRES: list[str] = [
    "pop.ballad", "pop.city_pop", "folk.acoustic", "rock.band", "rock.pop_punk",
    "rnb.soul", "electronic.dance", "lofi.chill", "jazz.lounge", "cn.guofeng",
    "rock.anime", "electronic.synthwave", "hiphop.boom_bap", "hiphop.trap",
]

PRESETS: dict[str, Preset] = {p.id: p for p in (
    _GENERIC, _BALLAD, _CITY_POP, _FOLK, _ROCK, _POP_PUNK, _RNB, _DANCE, _LOFI, _JAZZ,
    _GUOFENG, _ANIME, _SYNTHWAVE, _BOOM_BAP, _TRAP,
)}


def get_preset(preset_id: str | None) -> Preset:
    """空 id → generic;未知 id 抛 ValueError(API 层转 422)。"""
    if not preset_id:
        return PRESETS["generic"]
    try:
        return PRESETS[preset_id]
    except KeyError as exc:
        raise ValueError(f"未知风格预设: {preset_id}") from exc
