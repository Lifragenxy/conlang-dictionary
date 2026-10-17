"""Built-in English–Chinese meanings offered during word creation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import chain


@dataclass(frozen=True, slots=True)
class Concept:
    """A natural-language meaning the constructed word can express."""

    english: str
    chinese: str
    category: str

    @property
    def label(self) -> str:
        return f"{self.english} — {self.chinese}"


_CONCEPT_DATA: dict[str, tuple[tuple[str, str], ...]] = {
    "People & pronouns": (
        ("I", "我"),
        ("you", "你"),
        ("he", "他"),
        ("she", "她"),
        ("we", "我们"),
        ("they", "他们"),
        ("person", "人"),
        ("friend", "朋友"),
        ("child", "孩子"),
    ),
    "Nature": (
        ("water", "水"),
        ("fire", "火"),
        ("sun", "太阳"),
        ("moon", "月亮"),
        ("star", "星星"),
        ("sky", "天空"),
        ("earth", "土地"),
        ("wind", "风"),
        ("tree", "树"),
        ("flower", "花"),
        ("bird", "鸟"),
        ("fish", "鱼"),
        ("stone", "石头"),
        ("mountain", "山"),
    ),
    "Body & animals": (
        ("head", "头"),
        ("eye", "眼睛"),
        ("hand", "手"),
        ("heart", "心"),
        ("dog", "狗"),
        ("cat", "猫"),
        ("horse", "马"),
    ),
    "Actions": (
        ("be", "是"),
        ("have", "有"),
        ("go", "去"),
        ("come", "来"),
        ("eat", "吃"),
        ("drink", "喝"),
        ("see", "看"),
        ("hear", "听"),
        ("speak", "说"),
        ("know", "知道"),
        ("love", "爱"),
        ("sleep", "睡觉"),
    ),
    "Qualities & time": (
        ("big", "大"),
        ("small", "小"),
        ("good", "好"),
        ("bad", "坏"),
        ("new", "新"),
        ("old", "旧"),
        ("hot", "热"),
        ("cold", "冷"),
        ("day", "白天"),
        ("night", "夜晚"),
    ),
    "Numbers & quantity": (
        ("one", "一"),
        ("two", "二"),
        ("three", "三"),
        ("many", "许多"),
        ("all", "全部"),
    ),
}

CATEGORIES: tuple[str, ...] = tuple(_CONCEPT_DATA)
_CONCEPTS_BY_CATEGORY: dict[str, tuple[Concept, ...]] = {
    category: tuple(Concept(english, chinese, category) for english, chinese in pairs)
    for category, pairs in _CONCEPT_DATA.items()
}
ALL_CONCEPTS: tuple[Concept, ...] = tuple(
    chain.from_iterable(_CONCEPTS_BY_CATEGORY.values())
)


def concepts_in(category: str) -> tuple[Concept, ...]:
    """Return the concepts in one built-in category."""

    return _CONCEPTS_BY_CATEGORY.get(category, ())


def category_size(category: str) -> int:
    return len(_CONCEPTS_BY_CATEGORY.get(category, ()))


def search_concepts(query: str) -> tuple[Concept, ...]:
    """Search the built-in catalog by English, Chinese, or category name."""

    needle = query.strip().casefold()
    if not needle:
        return ()
    return tuple(
        concept
        for concept in ALL_CONCEPTS
        if needle in concept.english.casefold()
        or needle in concept.chinese
        or needle in concept.category.casefold()
    )
