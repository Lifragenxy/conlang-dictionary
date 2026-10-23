from __future__ import annotations

import unittest

from conlang_dict.concepts import (
    ALL_CONCEPTS,
    CORE_CATEGORY,
    CORE_CONCEPTS,
    CURATED_CATEGORIES,
    core_concepts_for_letter,
    core_letters,
    search_concepts,
)


class CatalogTests(unittest.TestCase):
    def test_catalog_is_substantial_and_unique(self) -> None:
        self.assertGreaterEqual(len(ALL_CONCEPTS), 2800)
        self.assertGreaterEqual(len(CORE_CONCEPTS), 2700)
        self.assertGreaterEqual(len(CURATED_CATEGORIES), 6)
        self.assertEqual(
            len({concept.key for concept in ALL_CONCEPTS}), len(ALL_CONCEPTS)
        )

    def test_common_concepts_are_present(self) -> None:
        by_word = {concept.english.casefold(): concept for concept in ALL_CONCEPTS}
        self.assertEqual(by_word["i"].chinese, "我")
        self.assertEqual(by_word["water"].chinese, "水")
        self.assertIn(by_word["water"].category, CURATED_CATEGORIES)
        self.assertTrue(by_word["abuse"].definition)
        self.assertIn("滥用", by_word["abuse"].chinese)
        self.assertEqual(by_word["the"].category, CORE_CATEGORY)

    def test_alphabetic_browsing(self) -> None:
        letters = core_letters()
        self.assertIn("A", letters)
        self.assertIn("W", letters)
        for word in core_concepts_for_letter("W"):
            self.assertTrue(word.english.upper().startswith("W"))

    def test_search_ranks_exact_match_first(self) -> None:
        results = search_concepts("I")
        self.assertTrue(results)
        self.assertEqual(results[0].english, "I")
        self.assertEqual(search_concepts("water")[0].english, "water")
        self.assertEqual(search_concepts("水")[0].english, "water")

    def test_search_matches_chinese_and_category(self) -> None:
        chinese = search_concepts("火")
        self.assertIn("fire", [concept.english for concept in chinese])
        nature = search_concepts("nature")
        self.assertTrue(nature)
        self.assertTrue(any(concept.category == "Nature" for concept in nature))


if __name__ == "__main__":
    unittest.main()
