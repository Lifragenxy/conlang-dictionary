from __future__ import annotations

import unittest

from conlang_dict.similarity import (
    damerau_levenshtein,
    is_similar,
    similarity_ratio,
    similarity_score,
)


class EditDistanceTests(unittest.TestCase):
    def test_identical_and_empty_strings(self) -> None:
        self.assertEqual(damerau_levenshtein("", ""), 0)
        self.assertEqual(damerau_levenshtein("vela", "vela"), 0)
        self.assertEqual(damerau_levenshtein("", "vela"), 4)
        self.assertEqual(damerau_levenshtein("vela", ""), 4)

    def test_single_edits(self) -> None:
        self.assertEqual(damerau_levenshtein("cat", "cut"), 1)
        self.assertEqual(damerau_levenshtein("vela", "velar"), 1)
        self.assertEqual(damerau_levenshtein("vela", "vel"), 1)

    def test_adjacent_transposition_costs_one(self) -> None:
        self.assertEqual(damerau_levenshtein("ab", "ba"), 1)

    def test_known_distance(self) -> None:
        self.assertEqual(damerau_levenshtein("kitten", "sitting"), 3)

    def test_case_insensitive(self) -> None:
        self.assertEqual(damerau_levenshtein("Vela", "vela"), 0)


class SimilarityTests(unittest.TestCase):
    def test_similar_near_spellings(self) -> None:
        self.assertTrue(is_similar("vela", "velar"))
        self.assertTrue(is_similar("katt", "kat"))
        self.assertTrue(is_similar("shae", "sha"))
        self.assertTrue(is_similar("Vela", "VELAR"))

    def test_unrelated_spellings_are_not_hinted(self) -> None:
        self.assertFalse(is_similar("cat", "dog"))
        self.assertFalse(is_similar("a", "b"))
        self.assertFalse(is_similar("vela", "vela"))

    def test_score_returns_distance_and_ratio(self) -> None:
        distance, ratio = similarity_score("vela", "velar")
        self.assertEqual(distance, 1)
        self.assertGreater(ratio, 0.8)
        self.assertAlmostEqual(similarity_ratio("abc", "abc"), 1.0)


if __name__ == "__main__":
    unittest.main()
