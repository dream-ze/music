# src/vocal_timbres.py
"""人声音色表:前端显示中文,写进 caption 的是英文短语。

keywords 用于校验 caption 是否真的写了这个音色;section_tags 给歌词段落标签加修饰,
如 {"Chorus": "powerful"} → [Chorus - powerful](只改不带修饰的标签,见 lyric_text)。
"""
from pydantic import BaseModel, Field


class VocalTimbre(BaseModel):
    id: str
    label: str
    caption: str
    keywords: list[str]
    section_tags: dict[str, str] = Field(default_factory=dict)


_ALL = [
    VocalTimbre(id="clear", label="清亮", caption="bright, clear vocal",
                keywords=["clear", "bright"]),
    VocalTimbre(id="breathy", label="气声", caption="breathy, airy vocal",
                keywords=["breathy", "airy"], section_tags={"Verse": "breathy"}),
    # 不用 gritty 当关键词:它常被当作质感词出现,会让音色校验误判通过
    VocalTimbre(id="raspy", label="烟嗓", caption="raspy, husky vocal",
                keywords=["raspy", "husky"]),
    VocalTimbre(id="deep", label="低沉磁性", caption="deep, warm low-register vocal",
                keywords=["deep", "low-register", "baritone"]),
    VocalTimbre(id="powerful", label="高亢有力", caption="powerful, belting vocal",
                keywords=["powerful", "belting"], section_tags={"Chorus": "powerful"}),
    VocalTimbre(id="falsetto", label="假声", caption="delicate falsetto vocal",
                keywords=["falsetto"], section_tags={"Chorus": "falsetto"}),
    VocalTimbre(id="soft_whisper", label="温柔耳语", caption="soft, hushed, whispered vocal",
                keywords=["whisper", "hushed"], section_tags={"Verse": "whispered"}),
    VocalTimbre(id="theatrical", label="戏剧化", caption="theatrical, dramatic vocal",
                keywords=["theatrical", "dramatic", "soaring"],
                section_tags={"Chorus": "soaring"}),
    VocalTimbre(id="rap_rapid", label="快嘴说唱", caption="rapid-fire rap flow",
                keywords=["rapid-fire", "rapid", "fast rap"], section_tags={"Verse": "rap"}),
    VocalTimbre(id="rap_laidback", label="慵懒说唱", caption="laid-back, relaxed rap flow",
                keywords=["laid-back", "relaxed"], section_tags={"Verse": "rap"}),
    VocalTimbre(id="choir", label="合唱", caption="layered choir harmonies",
                keywords=["choir"], section_tags={"Chorus": "choir"}),
]

TIMBRES: dict[str, VocalTimbre] = {t.id: t for t in _ALL}


def get_timbre(timbre_id: str | None) -> VocalTimbre | None:
    """空 → None(不指定);未知 id 抛 ValueError(API 层转 422)。"""
    if not timbre_id:
        return None
    try:
        return TIMBRES[timbre_id]
    except KeyError as exc:
        raise ValueError(f"未知人声音色: {timbre_id}") from exc
