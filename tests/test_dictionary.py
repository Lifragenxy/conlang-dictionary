from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from conlang_dict.dictionary import (
    AmbiguousEntryError,
    DuplicateWordError,
    Entry,
    EntryNotFoundError,
    Lexicon,
    LexiconFileError,
    ValidationError,
    validate_word,
)


class WordValidationTests(unittest.TestCase):
    def test_valid_ascii_words(self) -> None:
        for word in ("vela", "tlhIngan-Hol", "o'neil", "A", "x-y-z"):
            with self.subTest(word=word):
                self.assertEqual(validate_word(word), word)

    def test_outer_whitespace_is_trimmed(self) -> None:
        self.assertEqual(validate_word("  vela  "), "vela")

    def test_invalid_words(self) -> None:
        cases = {
            "": "empty",
            "   ": "empty",
            "two words": "letters",
            "w0rd": "digits",
            "café": "ASCII",
            "日本": "ASCII",
            "-vela": "leading",
            "vela-": "trailing",
            "ve--la": "punctuation",
            "x" * 65: "64",
        }
        for word, message in cases.items():
            with self.subTest(word=word):
                with self.assertRaises(ValidationError) as context:
                    validate_word(word)
                self.assertIn(message.casefold(), str(context.exception).casefold())


class LexiconTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.path = Path(self.td.name) / "data" / "lexicon.json"
        self.lexicon = Lexicon.load(self.path)

    def add_vela(self, word: str = "vela") -> Entry:
        return self.lexicon.add(word, "water", "水", "from the river")

    def test_missing_file_is_an_empty_dictionary(self) -> None:
        self.assertEqual(len(self.lexicon), 0)
        self.assertFalse(self.path.exists())

    def test_add_persists_json_and_reloads(self) -> None:
        entry = self.add_vela()
        self.assertTrue(self.path.exists())
        self.assertEqual(entry.id, 1)
        self.assertEqual(entry.pair, "water — 水")

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["format"], "conlang-lexicon")
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["entries"][0]["word"], "vela")
        self.assertIn("水", self.path.read_text(encoding="utf-8"))

        loaded = Lexicon.load(self.path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded.entries[0], entry)
        self.assertEqual(loaded.entries[0].notes, "from the river")

    def test_duplicate_word_is_rejected_case_insensitively(self) -> None:
        self.add_vela()
        with self.assertRaises(DuplicateWordError) as context:
            self.lexicon.add("VELA", "sea", "海")
        self.assertEqual(context.exception.existing.word, "vela")
        self.assertEqual(len(self.lexicon), 1)
        self.assertEqual(len(Lexicon.load(self.path)), 1)

    def test_synonyms_are_allowed(self) -> None:
        self.add_vela()
        second = self.lexicon.add("aqua", "water", "水")
        self.assertEqual(second.english, "water")
        self.assertEqual(second.chinese, "水")
        self.assertEqual(len(self.lexicon), 2)

    def test_ids_are_not_reused_after_delete_and_reload(self) -> None:
        first = self.add_vela("vela")
        second = self.lexicon.add("kando", "fire", "火")
        self.lexicon.delete(second.id)
        third = self.lexicon.add("mira", "star", "星星")
        self.assertEqual(first.id, 1)
        self.assertEqual(third.id, 3)

        reloaded = Lexicon.load(self.path)
        fourth = reloaded.add("suno", "sun", "太阳")
        self.assertEqual(fourth.id, 4)

    def test_update_fields_and_persistence(self) -> None:
        entry = self.add_vela()
        updated = self.lexicon.update(
            entry.id,
            word="velar",
            english="sea",
            chinese="海",
            notes="changed",
        )
        self.assertEqual(updated.word, "velar")
        self.assertEqual(updated.english, "sea")
        self.assertEqual(updated.chinese, "海")
        self.assertEqual(updated.notes, "changed")
        self.assertEqual(updated.created_at, entry.created_at)
        self.assertEqual(updated.id, entry.id)

        loaded = Lexicon.load(self.path)
        self.assertEqual(loaded.entries[0], updated)

    def test_update_to_duplicate_is_rejected_and_rolled_back(self) -> None:
        self.add_vela()
        other = self.lexicon.add("kando", "fire", "火")
        with self.assertRaises(DuplicateWordError):
            self.lexicon.update(other.id, word="VELA")
        self.assertEqual(self.lexicon.get(other.id).word, "kando")
        self.assertEqual(Lexicon.load(self.path).get(other.id).word, "kando")

    def test_update_can_clear_notes(self) -> None:
        entry = self.add_vela()
        updated = self.lexicon.update(entry.id, notes="")
        self.assertEqual(updated.notes, "")
        self.assertEqual(Lexicon.load(self.path).entries[0].notes, "")

    def test_update_with_no_changes_returns_same_entry(self) -> None:
        entry = self.add_vela()
        updated = self.lexicon.update(entry.id, word="vela", notes=entry.notes)
        self.assertEqual(updated, entry)

    def test_delete_persists(self) -> None:
        entry = self.add_vela()
        deleted = self.lexicon.delete(entry.id)
        self.assertEqual(deleted, entry)
        self.assertEqual(len(self.lexicon), 0)
        self.assertEqual(len(Lexicon.load(self.path)), 0)
        with self.assertRaises(EntryNotFoundError):
            self.lexicon.delete(entry.id)

    def test_resolve_by_id_word_gloss_and_unique_partial(self) -> None:
        vela = self.add_vela()
        kando = self.lexicon.add("kando", "fire", "火")

        self.assertEqual(self.lexicon.resolve("1"), vela)
        self.assertEqual(self.lexicon.resolve("VELA"), vela)
        self.assertEqual(self.lexicon.resolve("fire"), kando)
        self.assertEqual(self.lexicon.resolve("火"), kando)
        self.assertEqual(self.lexicon.resolve("kan"), kando)
        with self.assertRaises(EntryNotFoundError):
            self.lexicon.resolve("nothing-here")

    def test_ambiguous_gloss_reports_candidates(self) -> None:
        self.add_vela()
        aqua = self.lexicon.add("aqua", "water", "水")
        with self.assertRaises(AmbiguousEntryError) as context:
            self.lexicon.resolve("water")
        self.assertEqual(
            {entry.id for entry in context.exception.matches},
            {1, aqua.id},
        )

    def test_search_checks_all_fields(self) -> None:
        self.add_vela()
        self.lexicon.add("kando", "fire", "火", "warm")
        self.assertEqual(len(self.lexicon.search("vel")), 1)
        self.assertEqual(len(self.lexicon.search("水")), 1)
        self.assertEqual(len(self.lexicon.search("warm")), 1)
        self.assertEqual(len(self.lexicon.search("absent")), 0)

    def test_similar_words_are_sorted_limited_and_excludable(self) -> None:
        kata = self.lexicon.add("kata", "cat", "猫")
        kato = self.lexicon.add("kato", "dog", "狗")
        self.lexicon.add("vela", "water", "水")
        suggestions = self.lexicon.similar_words("katt")
        self.assertEqual(
            [item.entry.word for item in suggestions], ["kata", "kato"]
        )
        self.assertTrue(all(item.distance == 1 for item in suggestions))

        excluded = self.lexicon.similar_words("kata", exclude_id=kata.id)
        self.assertNotIn(kata.id, [item.entry.id for item in excluded])

        self.assertEqual(len(self.lexicon.similar_words("katt", limit=1)), 1)
        self.assertEqual(self.lexicon.similar_words("zzzzzz"), ())

    def test_corrupt_json_is_rejected(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(LexiconFileError) as context:
            Lexicon.load(self.path)
        self.assertIn("not valid JSON", str(context.exception))

    def test_unsupported_version_is_rejected(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps(
                {
                    "format": "conlang-lexicon",
                    "version": 99,
                    "entries": [],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(LexiconFileError) as context:
            Lexicon.load(self.path)
        self.assertIn("unsupported", str(context.exception))

    def test_duplicate_words_in_file_are_rejected(self) -> None:
        entry = {
            "id": 1,
            "word": "vela",
            "english": "water",
            "chinese": "水",
            "notes": "",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        duplicate = dict(entry, id=2, word="VELA")
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps(
                {
                    "format": "conlang-lexicon",
                    "version": 1,
                    "next_id": 3,
                    "entries": [entry, duplicate],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with self.assertRaises(LexiconFileError) as context:
            Lexicon.load(self.path)
        self.assertIn("duplicates", str(context.exception))

    def test_invalid_entry_in_file_is_rejected(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps(
                {
                    "format": "conlang-lexicon",
                    "version": 1,
                    "entries": [
                        {
                            "id": 1,
                            "word": "two words",
                            "english": "water",
                            "chinese": "水",
                            "created_at": "2026-01-01T00:00:00Z",
                            "updated_at": "2026-01-01T00:00:00Z",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(LexiconFileError):
            Lexicon.load(self.path)


if __name__ == "__main__":
    unittest.main()
