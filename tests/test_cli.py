from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.data = Path(self.td.name) / "dictionary.json"

    def run_cli(self, args: list[str], input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "conlang_dict",
                "--file",
                str(self.data),
                "--no-color",
                *args,
            ],
            cwd=ROOT,
            env=env,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )

    def quick_add(
        self,
        word: str = "vela",
        english: str = "water",
        chinese: str = "水",
    ) -> subprocess.CompletedProcess[str]:
        return self.run_cli(
            [
                "create",
                "--word",
                word,
                "--english",
                english,
                "--chinese",
                chinese,
            ]
        )

    def test_quick_create_and_persist(self) -> None:
        result = self.quick_add()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Added "vela" (#1)', result.stdout)
        self.assertIn("water — 水", result.stdout)
        self.assertIn("No existing words have a similar spelling.", result.stdout)

        payload = json.loads(self.data.read_text(encoding="utf-8"))
        self.assertEqual(payload["entries"][0]["word"], "vela")
        self.assertEqual(payload["entries"][0]["chinese"], "水")

    def test_duplicate_is_rejected(self) -> None:
        self.assertEqual(self.quick_add().returncode, 0)
        result = self.quick_add(word="VELA", english="sea", chinese="海")
        self.assertEqual(result.returncode, 1)
        self.assertIn("already in the dictionary", result.stdout)
        self.assertIn("uniqueness ignores capitalization", result.stdout)
        payload = json.loads(self.data.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["entries"]), 1)

    def test_similar_spelling_is_hinted_after_create(self) -> None:
        self.assertEqual(self.quick_add("kata", "cat", "猫").returncode, 0)
        result = self.quick_add("katt", "cat", "猫")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Similar existing spellings:", result.stdout)
        self.assertIn('"kata" (#1)', result.stdout)

    def test_guided_create_rejects_duplicate_and_can_cancel(self) -> None:
        self.assertEqual(self.quick_add().returncode, 0)
        result = self.run_cli(
            ["create"],
            input_text="s\nfire\nVELA\n\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Selected meaning: fire — 火", result.stdout)
        self.assertIn("already in the dictionary", result.stdout)
        self.assertIn("Creation cancelled.", result.stdout)
        payload = json.loads(self.data.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["entries"]), 1)

    def test_guided_create_warns_about_similar_spelling(self) -> None:
        self.assertEqual(self.quick_add().returncode, 0)
        result = self.run_cli(
            ["create"],
            input_text="s\nfire\nvelar\ny\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Similar existing spellings", result.stdout)
        self.assertIn("vela (#1)", result.stdout)
        self.assertIn('Added "velar" (#2): fire — 火', result.stdout)
        self.assertIn(
            'Similar existing spellings: "vela" (#1).', result.stdout
        )

    def test_mapped_meanings_are_hidden_from_picker(self) -> None:
        self.assertEqual(self.quick_add().returncode, 0)
        result = self.run_cli(
            ["create"],
            input_text="2\n0\nb\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Nature (14, 1 mapped)", result.stdout)
        self.assertIn("13 available", result.stdout)
        self.assertIn("1 mapped hidden", result.stdout)
        self.assertNotIn("water — 水", result.stdout)

    def test_mapped_search_is_blocked_until_shown(self) -> None:
        self.assertEqual(self.quick_add().returncode, 0)
        result = self.run_cli(
            ["create"],
            input_text="s\nwater\nb\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already mapped", result.stdout)
        self.assertIn("Press m", result.stdout)

    def test_mapped_meaning_can_be_shown_for_synonym(self) -> None:
        self.assertEqual(self.quick_add().returncode, 0)
        result = self.run_cli(
            ["create"],
            input_text="m\ns\nwater\nn\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("now visible", result.stdout)
        self.assertIn("Already mapped", result.stdout)
        self.assertIn("Create another word", result.stdout)
        self.assertIn("No word was created.", result.stdout)

    def test_catalog_browse_by_letter(self) -> None:
        result = self.run_cli(
            ["create"],
            input_text="7\nW\n0\n0\nb\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("General vocabulary", result.stdout)
        self.assertIn("browse by letter", result.stdout)
        self.assertIn("available", result.stdout)

    def test_ascii_validation(self) -> None:
        result = self.quick_add(word="café")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ASCII", result.stdout)

    def test_partial_quick_create_flags_are_rejected(self) -> None:
        result = self.run_cli(["create", "--word", "vela"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("must be supplied together", result.stdout)

    def test_list_show_search_update_delete(self) -> None:
        self.assertEqual(self.quick_add().returncode, 0)
        self.assertEqual(
            self.quick_add("kando", "fire", "火").returncode, 0
        )

        listing = self.run_cli(["list"])
        self.assertEqual(listing.returncode, 0)
        self.assertIn("Dictionary · 2 words", listing.stdout)
        self.assertIn("vela", listing.stdout)
        self.assertIn("water", listing.stdout)
        self.assertIn("水", listing.stdout)

        shown = self.run_cli(["show", "vela"])
        self.assertEqual(shown.returncode, 0)
        self.assertIn("#1 · vela", shown.stdout)
        self.assertIn("English", shown.stdout)
        self.assertIn("water", shown.stdout)
        self.assertIn("中文", shown.stdout)

        updated = self.run_cli(
            [
                "update",
                "vela",
                "--english",
                "sea",
                "--chinese",
                "海",
                "--notes",
                "river word",
            ]
        )
        self.assertEqual(updated.returncode, 0)
        self.assertIn('Updated "vela" (#1): sea — 海', updated.stdout)

        searched = self.run_cli(["search", "海"])
        self.assertEqual(searched.returncode, 0)
        self.assertIn("Search", searched.stdout)
        self.assertIn("vela", searched.stdout)

        deleted = self.run_cli(["delete", "vela", "--yes"])
        self.assertEqual(deleted.returncode, 0)
        self.assertIn('Deleted "vela" (#1)', deleted.stdout)

        remaining = self.run_cli(["list"])
        self.assertIn("Dictionary · 1 word", remaining.stdout)
        self.assertNotIn("vela", remaining.stdout)

    def test_clear_notes_flag(self) -> None:
        self.assertEqual(self.quick_add().returncode, 0)
        noted = self.run_cli(
            ["update", "vela", "--notes", "river word"]
        )
        self.assertEqual(noted.returncode, 0)

        cleared = self.run_cli(["update", "vela", "--clear-notes"])
        self.assertEqual(cleared.returncode, 0)
        payload = json.loads(self.data.read_text(encoding="utf-8"))
        self.assertEqual(payload["entries"][0]["notes"], "")

        shown = self.run_cli(["show", "vela"])
        self.assertNotIn("river word", shown.stdout)

    def test_interactive_update_and_delete_cancel(self) -> None:
        self.assertEqual(self.quick_add().returncode, 0)

        updated = self.run_cli(
            ["update", "vela"],
            input_text="\nsea\n海洋\n\n",
        )
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertIn('Updated "vela" (#1): sea — 海洋', updated.stdout)

        cancelled = self.run_cli(["delete", "vela"], input_text="n\n")
        self.assertEqual(cancelled.returncode, 0)
        self.assertIn("Deletion cancelled.", cancelled.stdout)
        shown = self.run_cli(["show", "vela"])
        self.assertEqual(shown.returncode, 0)

    def test_interactive_menu_quit(self) -> None:
        result = self.run_cli([], input_text="8\n")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Conlang Lexicon", result.stdout)
        self.assertIn("Statistics", result.stdout)
        self.assertIn("Goodbye.", result.stdout)

    def test_stats_command(self) -> None:
        self.assertEqual(self.quick_add().returncode, 0)
        self.assertEqual(
            self.quick_add("kando", "fire", "火").returncode, 0
        )
        result = self.run_cli(["stats", "--days", "7", "--top", "10"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Dictionary statistics", result.stdout)
        self.assertIn("Character frequency", result.stdout)
        self.assertIn("Contribution per day", result.stdout)
        self.assertIn("2 words", result.stdout)
        self.assertIn("created in this period", result.stdout)

    def test_stats_rejects_out_of_range_options(self) -> None:
        result = self.run_cli(["stats", "--days", "0"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("--days must be between", result.stdout)

    def test_missing_entry_reports_similar_spelling(self) -> None:
        self.assertEqual(self.quick_add("vela", "water", "水").returncode, 0)
        result = self.run_cli(["show", "velar"])
        self.assertEqual(result.returncode, 1)
        self.assertIn('No entry matches "velar"', result.stdout)
        self.assertIn("Similar spellings:", result.stdout)
        self.assertIn("vela (#1)", result.stdout)

    def test_corrupt_dictionary_is_reported_without_traceback(self) -> None:
        self.data.write_text("{broken", encoding="utf-8")
        result = self.run_cli(["list"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("not valid JSON", result.stdout)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
