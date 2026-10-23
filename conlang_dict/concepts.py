"""English–Chinese meaning catalog used during word creation.

The catalog bundles the NGSL 1.2 headword list with English definitions and
concise Chinese glosses.  A small hand-curated set of common concepts keeps
the topical categories (people, nature, actions, etc.) useful for quick
browsing; every other NGSL headword lives in the General vocabulary category.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CORE_CATEGORY = "General vocabulary"
_DATA_FILE = Path(__file__).with_name("data") / "concepts.json"


@dataclass(frozen=True, slots=True)
class Concept:
    """A natural-language meaning the constructed word can express."""

    english: str
    chinese: str
    category: str
    definition: str = ""

    @property
    def label(self) -> str:
        return f"{self.english} — {self.chinese}"

    @property
    def key(self) -> str:
        return self.english.casefold()


def _load_concepts() -> tuple[Concept, ...]:
    try:
        payload = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not load the bundled meaning catalog at {_DATA_FILE}: {exc}"
        ) from exc

    records = payload.get("concepts")
    if not isinstance(records, list):
        raise RuntimeError("The bundled meaning catalog is malformed.")

    concepts: list[Concept] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        english = str(record.get("english", "")).strip()
        chinese = str(record.get("chinese", "")).strip()
        category = str(record.get("category", "")).strip()
        definition = str(record.get("definition", "")).strip()
        if not english or not chinese or not category:
            continue
        key = english.casefold()
        if key in seen:
            continue
        seen.add(key)
        concepts.append(
            Concept(
                english=english,
                chinese=chinese,
                category=category,
                definition=definition,
            )
        )
    return tuple(concepts)


ALL_CONCEPTS: tuple[Concept, ...] = _load_concepts()
CATEGORIES: tuple[str, ...] = tuple(
    dict.fromkeys(concept.category for concept in ALL_CONCEPTS)
)
CURATED_CATEGORIES: tuple[str, ...] = tuple(
    category for category in CATEGORIES if category != CORE_CATEGORY
)
CONCEPTS_BY_CATEGORY: dict[str, tuple[Concept, ...]] = {
    category: tuple(
        concept for concept in ALL_CONCEPTS if concept.category == category
    )
    for category in CATEGORIES
}
CORE_CONCEPTS: tuple[Concept, ...] = CONCEPTS_BY_CATEGORY.get(CORE_CATEGORY, ())


def _letter_for(concept: Concept) -> str:
    first = concept.english[:1].upper()
    return first if "A" <= first <= "Z" else "#"


CORE_BY_LETTER: dict[str, tuple[Concept, ...]] = {
    letter: tuple(
        concept
        for concept in CORE_CONCEPTS
        if _letter_for(concept) == letter
    )
    for letter in sorted({_letter_for(concept) for concept in CORE_CONCEPTS})
}


def concepts_in(category: str) -> tuple[Concept, ...]:
    """Return the concepts in one category."""

    return CONCEPTS_BY_CATEGORY.get(category, ())


def category_size(category: str) -> int:
    return len(CONCEPTS_BY_CATEGORY.get(category, ()))


def core_letters() -> tuple[str, ...]:
    return tuple(CORE_BY_LETTER)


def core_concepts_for_letter(letter: str) -> tuple[Concept, ...]:
    return CORE_BY_LETTER.get(letter.upper(), ())


def search_concepts(query: str) -> tuple[Concept, ...]:
    """Search the catalog by English, Chinese, or category name.

    Results are ranked so exact English matches come first, then English
    prefix/substring matches, exact and partial Chinese matches, and finally
    category matches.
    """

    needle = query.strip().casefold()
    if not needle:
        return ()

    ranked: list[tuple[int, int, str, Concept]] = []
    for concept in ALL_CONCEPTS:
        english = concept.english.casefold()
        if english == needle:
            rank = 0
        elif english.startswith(needle):
            rank = 1
        elif needle in english:
            rank = 2
        elif concept.chinese == needle:
            rank = 3
        elif concept.chinese.startswith(needle):
            rank = 4
        elif needle in concept.chinese:
            rank = 5
        elif needle in concept.category.casefold():
            rank = 6
        else:
            continue
        ranked.append((rank, len(concept.english), english, concept))

    ranked.sort(key=lambda item: item[:3])
    return tuple(item[3] for item in ranked)
