from __future__ import annotations

import unittest
from datetime import date

from conlang_dict.dictionary import Entry
from conlang_dict.stats import (
    character_frequencies,
    contributions_by_day,
    summarize,
)


def make_entry(
    entry_id: int,
    word: str,
    english: str,
    chinese: str,
    created_at: str,
) -> Entry:
    return Entry(
        id=entry_id,
        word=word,
        english=english,
        chinese=chinese,
        notes="",
        created_at=created_at,
        updated_at=created_at,
    )


class CharacterFrequencyTests(unittest.TestCase):
    def test_counts_are_case_insensitive(self) -> None:
        entries = (
            make_entry(1, "Vela", "water", "水", "2026-01-08T12:00:00Z"),
            make_entry(2, "kando", "fire", "火", "2026-01-09T12:00:00Z"),
        )
        counts = character_frequencies(entries)
        self.assertEqual(counts["a"], 2)
        self.assertEqual(counts["v"], 1)
        self.assertEqual(counts["k"], 1)
        self.assertEqual(counts["V"], 0)
        self.assertEqual(sum(counts.values()), 9)


class ContributionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = date(2026, 1, 10)
        self.entries = (
            make_entry(1, "vela", "water", "水", "2026-01-06T12:00:00Z"),
            make_entry(2, "kando", "fire", "火", "2026-01-08T12:00:00Z"),
            make_entry(3, "mira", "star", "星星", "2026-01-10T12:00:00Z"),
        )

    def test_daily_counts_include_zero_days(self) -> None:
        daily = contributions_by_day(self.entries, 5, today=self.today)
        self.assertEqual(
            [(item.day.isoformat(), item.count) for item in daily],
            [
                ("2026-01-06", 1),
                ("2026-01-07", 0),
                ("2026-01-08", 1),
                ("2026-01-09", 0),
                ("2026-01-10", 1),
            ],
        )

    def test_daily_counts_exclude_days_before_range(self) -> None:
        daily = contributions_by_day(self.entries, 2, today=self.today)
        self.assertEqual([item.count for item in daily], [0, 1])

    def test_invalid_day_span(self) -> None:
        with self.assertRaises(ValueError):
            contributions_by_day(self.entries, 0, today=self.today)


class SummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = date(2026, 1, 10)
        self.entries = (
            make_entry(1, "vela", "water", "水", "2026-01-08T12:00:00Z"),
            make_entry(2, "kando", "fire", "火", "2026-01-09T12:00:00Z"),
            make_entry(3, "mira", "star", "星星", "2026-01-09T12:00:00Z"),
        )

    def test_summary_metrics(self) -> None:
        summary = summarize(self.entries, today=self.today)
        self.assertEqual(summary.entries, 3)
        self.assertEqual(summary.distinct_meanings, 3)
        self.assertEqual(summary.total_characters, 13)
        self.assertEqual(summary.longest_word, "kando")
        self.assertEqual(summary.longest_word_length, 5)
        self.assertAlmostEqual(
            summary.average_word_length, 13 / 3
        )
        self.assertEqual(summary.active_days, 2)
        self.assertEqual(summary.first_created, date(2026, 1, 8))
        self.assertEqual(summary.latest_created, date(2026, 1, 9))
        self.assertEqual(summary.most_productive_day, date(2026, 1, 9))
        self.assertEqual(summary.most_productive_count, 2)

    def test_current_streak_includes_yesterday(self) -> None:
        summary = summarize(self.entries, today=self.today)
        self.assertEqual(summary.current_streak, 2)
        self.assertEqual(summary.longest_streak, 2)

    def test_current_streak_breaks_after_a_gap(self) -> None:
        entries = (
            make_entry(1, "vela", "water", "水", "2026-01-05T12:00:00Z"),
            make_entry(2, "kando", "fire", "火", "2026-01-06T12:00:00Z"),
        )
        summary = summarize(entries, today=self.today)
        self.assertEqual(summary.current_streak, 0)
        self.assertEqual(summary.longest_streak, 2)

    def test_empty_dictionary(self) -> None:
        summary = summarize((), today=self.today)
        self.assertEqual(summary.entries, 0)
        self.assertEqual(summary.total_characters, 0)
        self.assertEqual(summary.unique_characters, 0)
        self.assertEqual(summary.first_created, None)
        self.assertEqual(summary.current_streak, 0)
        self.assertEqual(summary.longest_streak, 0)


if __name__ == "__main__":
    unittest.main()
