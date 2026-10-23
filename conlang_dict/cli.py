"""Command-line interface for the Conlang Lexicon dictionary builder."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from . import __version__
from .concepts import (
    CORE_CATEGORY,
    CORE_CONCEPTS,
    CURATED_CATEGORIES,
    Concept,
    concepts_in,
    core_concepts_for_letter,
    core_letters,
    search_concepts,
)
from .dictionary import (
    AmbiguousEntryError,
    DuplicateWordError,
    Entry,
    EntryNotFoundError,
    Lexicon,
    LexiconError,
    ValidationError,
    WordSuggestion,
    clean_meaning,
    clean_notes,
    validate_word,
)
from .display import (
    Console,
    configure_stdio,
    display_path,
    display_width,
    format_timestamp,
    plural,
    truncate_display,
)
from .stats import (
    character_frequencies,
    contributions_by_day,
    summarize,
)

APP_NAME = "Conlang Lexicon"
TAGLINE = "A dictionary builder for invented languages"


class PromptCancelled(Exception):
    """The user pressed Ctrl+C at a prompt."""


class EndOfInput(Exception):
    """Input ended while a prompt was waiting."""


class CliUsageError(Exception):
    """The command-line arguments form an invalid combination."""


def ask(
    console: Console,
    prompt: str,
    *,
    default: str | None = None,
) -> str:
    """Prompt for a line, turning cancellation into a clean exception."""

    suffix = ""
    if default is not None:
        shown = truncate_display(default, 42) if default else "none"
        suffix = f" [{shown}]"

    try:
        raw = input(f"{console.cyan('?')} {prompt}{suffix}: ")
    except EOFError as exc:
        print()
        raise EndOfInput from exc
    except KeyboardInterrupt as exc:
        print()
        raise PromptCancelled from exc

    value = raw.strip()
    if not value and default is not None:
        return default
    return value


def ask_yes_no(console: Console, prompt: str, *, default: bool) -> bool:
    marker = "[Y/n]" if default else "[y/N]"
    while True:
        answer = ask(console, f"{prompt} {marker}")
        if not answer:
            return default
        lowered = answer.casefold()
        if lowered in {"y", "yes"}:
            return True
        if lowered in {"n", "no"}:
            return False
        console.error("Please answer y or n.")


def pause(console: Console) -> None:
    console.print()
    try:
        input("  " + console.dim("Press Enter to return to the menu..."))
    except EOFError as exc:
        raise EndOfInput from exc
    except KeyboardInterrupt as exc:
        raise PromptCancelled from exc


class App:
    """Actions and interactive flows for one loaded lexicon."""

    def __init__(self, lexicon: Lexicon, console: Console) -> None:
        self.lexicon = lexicon
        self.console = console

    # ------------------------------------------------------------------
    # Interactive menu
    # ------------------------------------------------------------------
    def run_menu(self) -> int:
        while True:
            self._show_menu()
            try:
                choice = ask(self.console, "Choose [1-8]").casefold()
            except PromptCancelled:
                self.console.blank()
                self.console.hint("Cancelled.")
                return 130
            except EndOfInput:
                self.console.blank()
                return 0

            if choice in {"8", "q", "quit", "exit"}:
                self.console.blank()
                self.console.hint("Goodbye.")
                return 0
            if choice not in {"1", "2", "3", "4", "5", "6", "7"}:
                self.console.error("Please choose a number from 1 to 8.")
                continue

            try:
                if choice == "1":
                    self.create_interactive()
                elif choice == "2":
                    self._run_list()
                elif choice == "3":
                    entry = self.prompt_for_entry("Show")
                    if entry is not None:
                        self.display_entry(entry)
                elif choice == "4":
                    entry = self.prompt_for_entry("Edit")
                    if entry is not None:
                        self.update_interactive(entry)
                elif choice == "5":
                    entry = self.prompt_for_entry("Delete")
                    if entry is not None:
                        self.delete_entry(entry, assume_yes=False)
                elif choice == "6":
                    query = ask(self.console, "Search word, English, 中文, or notes")
                    if query:
                        self._display_search(query)
                    else:
                        self.console.hint("Cancelled.")
                elif choice == "7":
                    self.display_stats()
            except PromptCancelled:
                self.console.blank()
                self.console.hint("Cancelled.")
                continue
            except EndOfInput:
                self.console.blank()
                return 0
            except LexiconError as exc:
                self.report_error(exc)
                continue
            except CliUsageError as exc:
                self.console.error(str(exc))
                continue

            if choice in {"2", "3", "6", "7"}:
                try:
                    pause(self.console)
                except PromptCancelled:
                    self.console.blank()
                    self.console.hint("Cancelled.")
                    return 130
                except EndOfInput:
                    self.console.blank()
                    return 0

    def _show_menu(self) -> None:
        count = len(self.lexicon)
        console = self.console
        console.print()
        console.print("  " + console.bold(console.cyan(APP_NAME)))
        console.print("  " + console.dim(TAGLINE))
        console.print("  " + console.dim("─" * 46))
        console.print(
            "  "
            + console.dim(
                f"{display_path(self.lexicon.path)}  ·  "
                f"{count} {plural(count, 'word')}"
            )
        )
        console.print()
        console.print("   1  Create a word")
        console.print("   2  List words")
        console.print("   3  Show a word")
        console.print("   4  Update a word")
        console.print("   5  Delete a word")
        console.print("   6  Search")
        console.print("   7  Statistics")
        console.print("   8  Quit")
        if count == 0:
            console.print()
            console.hint("The dictionary is empty. Start with option 1.")
        console.print()

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def cmd_create(self, args: argparse.Namespace) -> int:
        provided = (args.word, args.english, args.chinese)
        if all(value is not None for value in provided):
            self.create_quick(
                args.word,
                args.english,
                args.chinese,
                notes=args.notes or "",
            )
            return 0
        if any(value is not None for value in provided):
            raise CliUsageError(
                "--word, --english and --chinese must be supplied together "
                "for a non-interactive create."
            )
        if args.notes is not None:
            raise CliUsageError(
                "--notes may only be used together with --word, --english "
                "and --chinese."
            )
        self.create_interactive(assume_yes=args.yes)
        return 0

    def create_quick(
        self,
        word: str,
        english: str,
        chinese: str,
        *,
        notes: str = "",
    ) -> Entry:
        self.console.heading("Create a new word")
        entry = self.lexicon.add(word, english, chinese, notes)
        self.console.success(
            f'Added "{entry.word}" (#{entry.id}): {entry.pair}'
        )
        self._print_similarity_summary(entry.word, exclude_id=entry.id)
        return entry

    def create_interactive(self, *, assume_yes: bool = False) -> Entry | None:
        self.console.heading("Create a new word")
        self.console.print(
            "  "
            + self.console.dim(
                "Choose an English — 中文 meaning, then invent an ASCII spelling."
            )
        )

        concept = self.choose_concept()
        if concept is None:
            self.console.hint("No word was created.")
            return None

        self.console.blank()
        self.console.print(
            "  "
            + self.console.bold("Selected meaning: ")
            + concept.english
            + " — "
            + concept.chinese
        )
        if concept.definition:
            self.console.hint(f"Definition: {concept.definition}")

        existing = self.lexicon.entries_for_english(concept.english)
        if existing:
            refs = ", ".join(f'"{entry.word}" (#{entry.id})' for entry in existing)
            self.console.warning(f"Already mapped: {refs}.")
            if not ask_yes_no(
                self.console,
                "Create another word for this meaning (a synonym)?",
                default=False,
            ):
                self.console.hint("No word was created.")
                return None

        word = self.prompt_new_word(assume_yes=assume_yes)
        if word is None:
            self.console.hint("No word was created.")
            return None

        entry = self.lexicon.add(word, concept.english, concept.chinese)
        self.console.blank()
        self.console.success(
            f'Added "{entry.word}" (#{entry.id}): {entry.pair}'
        )
        self._print_similarity_summary(entry.word, exclude_id=entry.id)
        return entry

    def prompt_new_word(self, *, assume_yes: bool) -> str | None:
        while True:
            raw = ask(
                self.console,
                "New word (ASCII letters, optional internal - or ')",
            )
            if not raw:
                self.console.hint("Creation cancelled.")
                return None

            try:
                word = validate_word(raw)
            except ValidationError as exc:
                self.console.error(str(exc))
                continue

            duplicate = self.lexicon.duplicate_of(word)
            if duplicate is not None:
                self.report_error(DuplicateWordError(word, duplicate))
                self.console.hint("  Please choose a different spelling.")
                continue

            suggestions = self.lexicon.similar_words(word)
            if suggestions:
                self._show_suggestions(suggestions)
                if not assume_yes and not ask_yes_no(
                    self.console,
                    f'Create "{word}" anyway?',
                    default=True,
                ):
                    self.console.hint("  Please choose a different spelling.")
                    continue
            return word

    # ------------------------------------------------------------------
    # Concept picker
    # ------------------------------------------------------------------
    def choose_concept(self) -> Concept | None:
        mapped_keys = self.lexicon.mapped_english_keys()
        show_mapped = False

        while True:
            self.console.section("Choose a meaning (English — 中文)")
            for index, category in enumerate(CURATED_CATEGORIES, start=1):
                concepts = concepts_in(category)
                mapped = self._mapped_count(concepts, mapped_keys)
                suffix = f", {mapped} mapped" if mapped else ""
                self.console.print(
                    f"    {index:>2}  {category} ({len(concepts)}{suffix})"
                )

            core_index = len(CURATED_CATEGORIES) + 1
            core_mapped = self._mapped_count(CORE_CONCEPTS, mapped_keys)
            core_suffix = f", {core_mapped} mapped" if core_mapped else ""
            self.console.print(
                f"    {core_index:>2}  {CORE_CATEGORY} A–Z "
                f"({len(CORE_CONCEPTS)}{core_suffix})"
            )
            self.console.print("     s  Search all meanings")
            self.console.print("     c  Custom English — 中文 pair")
            self.console.print(
                "     m  "
                + ("Hide" if show_mapped else "Show")
                + " already-mapped meanings"
            )
            self.console.print("     b  Cancel")
            if not show_mapped and mapped_keys:
                self.console.hint(
                    "Already-mapped meanings are hidden by default."
                )

            choice = ask(
                self.console,
                f"Choose [1-{core_index}/s/c/m/b]",
            ).casefold()
            if choice in {"", "b", "back", "cancel"}:
                return None
            if choice in {"m", "mapped"}:
                show_mapped = not show_mapped
                if show_mapped:
                    self.console.hint(
                        "Already-mapped meanings are now visible and marked ✓."
                    )
                else:
                    self.console.hint("Already-mapped meanings are hidden again.")
                continue
            if choice in {"s", "search"}:
                concept = self.search_concept_ui(
                    mapped_keys, show_mapped=show_mapped
                )
                if concept is not None:
                    return concept
                continue
            if choice in {"c", "custom"}:
                return self.custom_concept()
            if choice.isdigit():
                number = int(choice)
                if 1 <= number <= len(CURATED_CATEGORIES):
                    category = CURATED_CATEGORIES[number - 1]
                    concepts = concepts_in(category)
                    mapped = self._mapped_count(concepts, mapped_keys)
                    if not show_mapped and mapped == len(concepts):
                        self.console.warning(
                            f"Every meaning in {category} is already mapped."
                        )
                        self.console.hint(
                            "Press m to show mapped meanings and choose one "
                            "for a synonym."
                        )
                        continue
                    concept = self.choose_in_category(
                        category,
                        mapped_keys=mapped_keys,
                        show_mapped=show_mapped,
                    )
                    if concept is not None:
                        return concept
                    continue
                if number == core_index:
                    if not show_mapped and core_mapped == len(CORE_CONCEPTS):
                        self.console.warning(
                            "Every General vocabulary meaning is already mapped."
                        )
                        self.console.hint(
                            "Press m to show mapped meanings and choose one "
                            "for a synonym."
                        )
                        continue
                    concept = self.browse_core(
                        mapped_keys, show_mapped=show_mapped
                    )
                    if concept is not None:
                        return concept
                    continue
            self.console.error(
                "Please choose a listed number, s, c, m, or b."
            )

    def choose_in_category(
        self,
        category: str,
        *,
        mapped_keys: frozenset[str],
        show_mapped: bool,
    ) -> Concept | None:
        return self._choose_from_list(
            concepts_in(category),
            category,
            mapped_keys=mapped_keys,
            show_mapped=show_mapped,
        )

    def browse_core(
        self,
        mapped_keys: frozenset[str],
        *,
        show_mapped: bool,
    ) -> Concept | None:
        letters = core_letters()
        while True:
            self.console.section(f"{CORE_CATEGORY} · browse by letter")
            for letter in letters:
                concepts = core_concepts_for_letter(letter)
                mapped = self._mapped_count(concepts, mapped_keys)
                suffix = f", {mapped} mapped" if mapped else ""
                self.console.print(
                    f"    {letter}  {len(concepts):>4} words{suffix}"
                )
            self.console.print("     0  Back")

            choice = ask(self.console, "Letter [A-Z/0]").upper()
            if choice in {"", "0", "BACK"}:
                return None
            if choice in letters:
                concepts = core_concepts_for_letter(choice)
                mapped = self._mapped_count(concepts, mapped_keys)
                if not show_mapped and mapped == len(concepts):
                    self.console.warning(
                        f"Every {choice} word in General vocabulary is already mapped."
                    )
                    self.console.hint(
                        "Press m to show mapped meanings and choose one for a synonym."
                    )
                    continue
                return self._choose_from_list(
                    concepts,
                    f"{CORE_CATEGORY} · {choice}",
                    mapped_keys=mapped_keys,
                    show_mapped=show_mapped,
                )
            self.console.error("Please choose a letter from A to Z, or 0.")

    def search_concept_ui(
        self,
        mapped_keys: frozenset[str],
        *,
        show_mapped: bool,
    ) -> Concept | None:
        query = ask(self.console, "Search English, 中文, or category")
        if not query:
            return None
        matches = search_concepts(query)
        if not matches:
            self.console.warning(f'No built-in meanings matched "{query}".')
            return None

        visible = self._visible_concepts(
            matches, mapped_keys, show_mapped=show_mapped
        )
        hidden = len(matches) - len(visible)
        if not visible:
            if len(matches) == 1:
                self.console.warning(
                    f'The meaning matching "{query}" is already mapped.'
                )
            else:
                self.console.warning(
                    f'All {len(matches)} meanings matching "{query}" '
                    "are already mapped."
                )
            self.console.hint(
                "Press m to show mapped meanings and choose one for a synonym."
            )
            return None

        if len(visible) == 1:
            concept = visible[0]
            self.console.print(
                "  "
                + self.console.green("Found: ")
                + f"{concept.english} — {concept.chinese}"
                + self.console.dim(f"  ({concept.category})")
            )
            if hidden:
                self.console.hint(
                    f"{hidden} already-mapped matching meaning"
                    f"{'s are' if hidden != 1 else ' is'} hidden."
                )
            return concept

        return self._choose_from_list(
            matches,
            f'Search results for "{query}"',
            mapped_keys=mapped_keys,
            show_mapped=show_mapped,
        )

    def _choose_from_list(
        self,
        concepts: tuple[Concept, ...],
        title: str,
        *,
        mapped_keys: frozenset[str],
        show_mapped: bool,
    ) -> Concept | None:
        visible = self._visible_concepts(
            concepts, mapped_keys, show_mapped=show_mapped
        )
        if not visible:
            self.console.warning("Every meaning in this list is already mapped.")
            self.console.hint(
                "Press m to show mapped meanings and choose one for a synonym."
            )
            return None

        page_size = 20
        total_pages = max(1, (len(visible) + page_size - 1) // page_size)
        page = 0
        hidden = len(concepts) - len(visible)

        while True:
            start = page * page_size
            page_items = visible[start : start + page_size]
            self.console.section(title)
            subtitle = (
                f"{len(visible)} available · page {page + 1}/{total_pages}"
            )
            if hidden and not show_mapped:
                subtitle += f" · {hidden} mapped hidden"
            self.console.hint(subtitle)

            for index, concept in enumerate(page_items, start=1):
                category = (
                    "  " + self.console.dim(f"({concept.category})")
                    if title.startswith("Search")
                    else ""
                )
                marker = (
                    "  " + self.console.dim("✓ already mapped")
                    if concept.key in mapped_keys
                    else ""
                )
                self.console.print(
                    f"    {index:>2}  {concept.english} — "
                    f"{concept.chinese}{category}{marker}"
                )

            if total_pages > 1:
                if page > 0:
                    self.console.print("     p  Previous page")
                if page < total_pages - 1:
                    self.console.print("     n  Next page")
            self.console.print("     0  Back")

            page_hint = ""
            if total_pages > 1:
                page_hint = "/n/p"
            choice = ask(
                self.console,
                f"Choose meaning [0-{len(page_items)}{page_hint}]",
            ).casefold()
            if choice in {"", "0", "b", "back"}:
                return None
            if choice in {"n", "next"}:
                if page < total_pages - 1:
                    page += 1
                    continue
                self.console.error("There is no next page.")
                continue
            if choice in {"p", "prev", "previous"}:
                if page > 0:
                    page -= 1
                    continue
                self.console.error("There is no previous page.")
                continue
            if choice.isdigit():
                number = int(choice)
                if 1 <= number <= len(page_items):
                    return page_items[number - 1]
            self.console.error(
                f"Please enter a number from 0 to {len(page_items)}"
                + (", n, or p." if total_pages > 1 else ".")
            )

    @staticmethod
    def _visible_concepts(
        concepts: tuple[Concept, ...],
        mapped_keys: frozenset[str],
        *,
        show_mapped: bool,
    ) -> tuple[Concept, ...]:
        if show_mapped:
            return tuple(concepts)
        return tuple(
            concept for concept in concepts if concept.key not in mapped_keys
        )

    @staticmethod
    def _mapped_count(
        concepts: tuple[Concept, ...],
        mapped_keys: frozenset[str],
    ) -> int:
        return sum(1 for concept in concepts if concept.key in mapped_keys)

    def custom_concept(self) -> Concept | None:
        self.console.section("Custom English — 中文 meaning")
        while True:
            raw_english = ask(self.console, "English meaning")
            if not raw_english:
                self.console.hint("Custom meaning cancelled.")
                return None
            try:
                english = clean_meaning(raw_english, "English meaning")
            except ValidationError as exc:
                self.console.error(str(exc))
                continue
            break

        while True:
            raw_chinese = ask(self.console, "中文 meaning")
            if not raw_chinese:
                self.console.hint("Custom meaning cancelled.")
                return None
            try:
                chinese = clean_meaning(raw_chinese, "中文 meaning")
            except ValidationError as exc:
                self.console.error(str(exc))
                continue
            break

        self.console.print(
            "  " + self.console.green("Using: ")
            + f"{english} — {chinese}"
        )
        return Concept(english=english, chinese=chinese, category="Custom")

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def cmd_list(self, args: argparse.Namespace) -> int:
        self._run_list(sort=args.sort)
        return 0

    def _run_list(self, *, sort: str = "word") -> None:
        entries = self.lexicon.entries
        if not entries:
            self.console.heading("Dictionary")
            self.console.print("  The dictionary is empty.")
            self.console.hint(
                "Choose Create in the menu, or run `create`, to add your first word."
            )
            return
        self.console.heading(
            f"Dictionary · {len(entries)} {plural(len(entries), 'word')}"
        )
        self.console.print(
            "  " + self.console.dim(display_path(self.lexicon.path))
        )
        self._print_table(entries, sort=sort)

    def cmd_show(self, args: argparse.Namespace) -> int:
        entry = self.lexicon.resolve(args.target)
        self.display_entry(entry)
        return 0

    def display_entry(self, entry: Entry) -> None:
        self.console.heading(f"#{entry.id} · {entry.word}")
        self._detail("English", entry.english)
        self._detail("中文", entry.chinese)
        self._detail(
            "Notes",
            entry.notes if entry.notes else self.console.dim("—"),
        )
        self._detail("Created", format_timestamp(entry.created_at))
        self._detail("Updated", format_timestamp(entry.updated_at))
        self.console.blank()

    def _detail(self, label: str, value: str, *, width: int = 10) -> None:
        padding = " " * max(0, width - display_width(label))
        self.console.print(
            f"  {self.console.bold(label)}{padding}  {value}"
        )

    def _print_table(
        self,
        entries: tuple[Entry, ...],
        *,
        sort: str = "word",
    ) -> None:
        sorters = {
            "word": lambda entry: (entry.word.casefold(), entry.id),
            "id": lambda entry: (entry.id,),
            "english": lambda entry: (
                entry.english.casefold(),
                entry.word.casefold(),
                entry.id,
            ),
            "chinese": lambda entry: (
                entry.chinese.casefold(),
                entry.word.casefold(),
                entry.id,
            ),
        }
        sorted_entries = sorted(entries, key=sorters[sort])
        rows = [
            (str(entry.id), entry.word, entry.english, entry.chinese)
            for entry in sorted_entries
        ]
        self.console.print_table(("#", "WORD", "ENGLISH", "中文"), rows)

    def cmd_search(self, args: argparse.Namespace) -> int:
        query = args.query.strip()
        if not query:
            raise CliUsageError("Search query cannot be empty.")
        self._display_search(query)
        return 0

    def _display_search(self, query: str) -> None:
        matches = self.lexicon.search(query)
        if not matches:
            self.console.heading(f'Search · "{query}"')
            self.console.warning("No entries matched.")
            self.console.hint("Try a shorter term, or search in English and 中文.")
            return
        self.console.heading(
            f'Search "{query}" · {len(matches)} {plural(len(matches), "match", "matches")}'
        )
        self._print_table(matches, sort="word")

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def cmd_stats(self, args: argparse.Namespace) -> int:
        if not 1 <= args.days <= 366:
            raise CliUsageError("--days must be between 1 and 366.")
        if not 1 <= args.top <= 100:
            raise CliUsageError("--top must be between 1 and 100.")
        self.display_stats(days=args.days, top=args.top)
        return 0

    def display_stats(self, *, days: int = 30, top: int = 20) -> None:
        entries = self.lexicon.entries
        if not entries:
            self.console.heading("Dictionary statistics")
            self.console.print("  The dictionary is empty.")
            self.console.hint("Add some words to see character and activity statistics.")
            return

        stats = summarize(entries)
        self.console.heading("Dictionary statistics")
        self.console.print(
            "  " + self.console.dim(display_path(self.lexicon.path))
        )
        self.console.blank()

        width = 18
        self._detail("Words", str(stats.entries), width=width)
        self._detail(
            "Distinct meanings", str(stats.distinct_meanings), width=width
        )
        self._detail(
            "Characters",
            f"{stats.total_characters} total · "
            f"{stats.unique_characters} unique",
            width=width,
        )
        self._detail(
            "Average length",
            f"{stats.average_word_length:.2f}",
            width=width,
        )
        self._detail(
            "Longest word",
            f'"{stats.longest_word}" ({stats.longest_word_length})',
            width=width,
        )
        self._detail("Active days", str(stats.active_days), width=width)
        self._detail(
            "Current streak",
            f"{stats.current_streak} "
            f"{plural(stats.current_streak, 'day')}",
            width=width,
        )
        self._detail(
            "Longest streak",
            f"{stats.longest_streak} "
            f"{plural(stats.longest_streak, 'day')}",
            width=width,
        )
        self._detail(
            "First entry",
            stats.first_created.isoformat() if stats.first_created else "—",
            width=width,
        )
        self._detail(
            "Latest entry",
            stats.latest_created.isoformat() if stats.latest_created else "—",
            width=width,
        )
        if stats.most_productive_day is not None:
            self._detail(
                "Best day",
                f"{stats.most_productive_day.isoformat()} "
                f"({stats.most_productive_count} "
                f"{plural(stats.most_productive_count, 'word')})",
                width=width,
            )

        self.console.section("Character frequency (case-insensitive)")
        self.console.hint(
            f"{stats.unique_characters} unique characters across "
            f"{stats.total_characters} characters."
        )
        frequencies = character_frequencies(entries)
        ranked = sorted(
            frequencies.items(), key=lambda item: (-item[1], item[0])
        )
        shown = ranked[:top]
        rows = [
            (
                str(index),
                character,
                str(count),
                f"{count / stats.total_characters * 100:.1f}%",
            )
            for index, (character, count) in enumerate(shown, start=1)
        ]
        self.console.print_table(
            ("#", "CHAR", "COUNT", "SHARE"),
            rows,
            caps=(4, 6, 8, 8),
            right_columns=(0, 2, 3),
        )
        if len(ranked) > len(shown):
            self.console.hint(
                f"Showing the top {len(shown)} of {len(ranked)} characters; "
                "use --top to show more."
            )

        daily = contributions_by_day(entries, days)
        max_count = max((item.count for item in daily), default=0)
        active_in_period = sum(1 for item in daily if item.count)
        total_in_period = sum(item.count for item in daily)
        bar_width = 24
        daily_rows = []
        for item in daily:
            if item.count:
                bar_length = max(
                    1, round(item.count / max_count * bar_width)
                )
                bar = "█" * bar_length
            else:
                bar = ""
            daily_rows.append(
                (item.day.isoformat(), str(item.count), bar)
            )

        self.console.section(
            f"Contribution per day · last {days} days (UTC)"
        )
        self.console.print_table(
            ("DATE", "WORDS", ""),
            daily_rows,
            caps=(12, 6, bar_width),
            right_columns=(1,),
        )
        self.console.hint(
            f"{total_in_period} {plural(total_in_period, 'word')} created "
            f"in this period on {active_in_period} "
            f"{plural(active_in_period, 'active day')}."
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def cmd_update(self, args: argparse.Namespace) -> int:
        entry = self.lexicon.resolve(args.target)
        clear_notes = bool(getattr(args, "clear_notes", False))
        notes = "" if clear_notes else args.notes
        provided = (args.word, args.english, args.chinese, notes)
        if all(value is None for value in provided):
            self.update_interactive(entry)
            return 0

        updated = self.lexicon.update(
            entry.id,
            word=args.word,
            english=args.english,
            chinese=args.chinese,
            notes=notes,
        )
        if updated == entry:
            self.console.info("No changes made.")
            return 0

        self.console.success(
            f'Updated "{updated.word}" (#{updated.id}): {updated.pair}'
        )
        if updated.word != entry.word:
            self._print_similarity_summary(updated.word, exclude_id=updated.id)
        return 0

    def update_interactive(self, entry: Entry) -> Entry | None:
        self.console.heading(f"Edit #{entry.id} · {entry.word}")
        self.console.print(f"  Current meaning: {entry.pair}")
        self.console.hint(
            "Press Enter to keep a field; enter - for notes to clear them."
        )

        new_word = entry.word
        while True:
            raw = ask(
                self.console,
                f"New word [{truncate_display(entry.word, 36)}]",
            )
            candidate = entry.word if not raw else raw
            if candidate == entry.word:
                break
            try:
                candidate = validate_word(candidate)
            except ValidationError as exc:
                self.console.error(str(exc))
                continue

            duplicate = self.lexicon.duplicate_of(
                candidate, exclude_id=entry.id
            )
            if duplicate is not None:
                self.report_error(DuplicateWordError(candidate, duplicate))
                continue

            suggestions = self.lexicon.similar_words(
                candidate, exclude_id=entry.id
            )
            if suggestions:
                self._show_suggestions(suggestions)
                if not ask_yes_no(
                    self.console,
                    f'Use "{candidate}" anyway?',
                    default=True,
                ):
                    self.console.hint("  Choose a different spelling.")
                    continue
            new_word = candidate
            break

        new_english = self._prompt_meaning_field("English", entry.english)
        new_chinese = self._prompt_meaning_field("中文", entry.chinese)

        while True:
            preview = (
                truncate_display(entry.notes, 40) if entry.notes else "none"
            )
            raw_notes = ask(self.console, f"Notes [{preview}]")
            if not raw_notes:
                new_notes = entry.notes
            elif raw_notes == "-":
                new_notes = ""
            else:
                new_notes = raw_notes
            try:
                new_notes = clean_notes(new_notes)
            except ValidationError as exc:
                self.console.error(str(exc))
                continue
            break

        updated = self.lexicon.update(
            entry.id,
            word=new_word,
            english=new_english,
            chinese=new_chinese,
            notes=new_notes,
        )
        if updated == entry:
            self.console.info("No changes made.")
            return None

        self.console.blank()
        self.console.success(
            f'Updated "{updated.word}" (#{updated.id}): {updated.pair}'
        )
        if updated.word != entry.word:
            self._print_similarity_summary(
                updated.word, exclude_id=updated.id
            )
        return updated

    def _prompt_meaning_field(self, label: str, current: str) -> str:
        while True:
            raw = ask(
                self.console,
                f"{label} [{truncate_display(current, 40)}]",
            )
            candidate = current if not raw else raw
            try:
                return clean_meaning(candidate, f"{label} meaning")
            except ValidationError as exc:
                self.console.error(str(exc))

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------
    def cmd_delete(self, args: argparse.Namespace) -> int:
        entry = self.lexicon.resolve(args.target)
        self.delete_entry(entry, assume_yes=args.yes)
        return 0

    def delete_entry(self, entry: Entry, *, assume_yes: bool) -> bool:
        if not assume_yes:
            confirmed = ask_yes_no(
                self.console,
                f'Delete "{entry.word}" (#{entry.id}) — {entry.pair}?',
                default=False,
            )
            if not confirmed:
                self.console.hint("Deletion cancelled.")
                return False

        deleted = self.lexicon.delete(entry.id)
        self.console.success(
            f'Deleted "{deleted.word}" (#{deleted.id}): {deleted.pair}'
        )
        return True

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def prompt_for_entry(self, action: str) -> Entry | None:
        while True:
            query = ask(
                self.console,
                f"{action} entry by ID, word, English, or 中文",
            )
            if not query:
                self.console.hint("Cancelled.")
                return None
            try:
                return self.lexicon.resolve(query)
            except (EntryNotFoundError, AmbiguousEntryError) as exc:
                self.report_error(exc)

    def _show_suggestions(
        self, suggestions: tuple[WordSuggestion, ...]
    ) -> None:
        self.console.section("Similar existing spellings")
        for suggestion in suggestions:
            entry = suggestion.entry
            self.console.print(
                f"    • {entry.word} (#{entry.id}) — {entry.pair}  "
                + self.console.dim(f"(distance {suggestion.distance})")
            )

    def _print_similarity_summary(
        self, word: str, *, exclude_id: int | None = None
    ) -> None:
        suggestions = self.lexicon.similar_words(
            word, exclude_id=exclude_id
        )
        if suggestions:
            names = ", ".join(
                f'"{suggestion.entry.word}" (#{suggestion.entry.id})'
                for suggestion in suggestions
            )
            self.console.print(
                "  "
                + self.console.dim(f"Similar existing spellings: {names}.")
            )
        else:
            self.console.print(
                "  "
                + self.console.dim("No existing words have a similar spelling.")
            )

    def report_error(self, exc: LexiconError) -> None:
        self.console.error(str(exc))
        if isinstance(exc, DuplicateWordError):
            self.console.hint("Word uniqueness ignores capitalization.")
        elif isinstance(exc, AmbiguousEntryError):
            self.console.hint("Use an entry ID or a more specific spelling:")
            for match in exc.matches:
                self.console.print(
                    f"      #{match.id:<3} {match.word}  ({match.pair})"
                )
        elif isinstance(exc, EntryNotFoundError):
            suggestions = self.lexicon.similar_words(exc.query, limit=3)
            if suggestions:
                self.console.hint("Similar spellings:")
                for suggestion in suggestions:
                    entry = suggestion.entry
                    self.console.print(
                        f"      {entry.word} (#{entry.id}) — {entry.pair}"
                    )


# ----------------------------------------------------------------------
# Parser and entry point
# ----------------------------------------------------------------------
def resolve_data_path(value: str | None) -> Path:
    raw = value or os.environ.get("CONLANG_DICT_FILE")
    if raw:
        return Path(raw).expanduser()
    return Path.cwd() / "data" / "dictionary.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="conlang-dict",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Build and maintain a dictionary for an artificial language.\n"
            "Every word is mapped to an English–Chinese meaning, must be "
            "spellable in ASCII,\nand must be unique. Near-identical "
            "spellings are flagged as hints."
        ),
        epilog=(
            "Run without a command for the interactive menu.\n"
            "The data file defaults to ./data/dictionary.json; override it "
            "with --file\nor the CONLANG_DICT_FILE environment variable.\n\n"
            "Examples:\n"
            "  conlang-dict\n"
            "  conlang-dict create\n"
            "  conlang-dict list\n"
            "  conlang-dict show 1\n"
            "  conlang-dict create --word vela --english water --chinese 水\n"
            "  conlang-dict update vela --english sea --chinese 海\n"
            "  conlang-dict stats\n"
            "  conlang-dict delete vela --yes"
        ),
    )
    parser.add_argument(
        "-f",
        "--file",
        "--data",
        dest="data_file",
        metavar="PATH",
        help=(
            "JSON dictionary file (default: ./data/dictionary.json; "
            "env: CONLANG_DICT_FILE)."
        ),
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colour even on a terminal.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        metavar="COMMAND",
    )

    create_parser = subparsers.add_parser(
        "create",
        aliases=["add", "new"],
        help="Create a word (guided by default).",
        description=(
            "Interactively choose an English–Chinese meaning and enter a new "
            "ASCII spelling. Supplying --word, --english and --chinese "
            "together performs a quick, non-interactive create."
        ),
    )
    create_parser.add_argument("--word", metavar="WORD")
    create_parser.add_argument("--english", metavar="MEANING")
    create_parser.add_argument("--chinese", metavar="MEANING")
    create_parser.add_argument(
        "--notes",
        metavar="TEXT",
        help="Optional notes (quick create only).",
    )
    create_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="In guided mode, skip the similar-spelling confirmation prompt.",
    )
    create_parser.set_defaults(func=App.cmd_create)

    list_parser = subparsers.add_parser(
        "list",
        aliases=["ls"],
        help="List all words.",
    )
    list_parser.add_argument(
        "--sort",
        choices=("word", "id", "english", "chinese"),
        default="word",
        help="Sort order (default: word).",
    )
    list_parser.set_defaults(func=App.cmd_list)

    show_parser = subparsers.add_parser(
        "show",
        aliases=["lookup"],
        help="Show one word and its details.",
    )
    show_parser.add_argument(
        "target",
        metavar="TARGET",
        help="Entry ID, exact word, English/中文 gloss, or unique partial match.",
    )
    show_parser.set_defaults(func=App.cmd_show)

    update_parser = subparsers.add_parser(
        "update",
        aliases=["edit"],
        help="Update a word (interactive by default).",
        description=(
            "With no field options, prompts for each field; press Enter to "
            "keep a value. Supplying any field option performs a direct update."
        ),
    )
    update_parser.add_argument(
        "target",
        metavar="TARGET",
        help="Entry ID, word, gloss, or unique partial match.",
    )
    update_parser.add_argument("--word", metavar="WORD")
    update_parser.add_argument("--english", metavar="MEANING")
    update_parser.add_argument("--chinese", metavar="MEANING")
    notes_group = update_parser.add_mutually_exclusive_group()
    notes_group.add_argument(
        "--notes",
        metavar="TEXT",
        help="New notes text.",
    )
    notes_group.add_argument(
        "--clear-notes",
        action="store_true",
        help="Clear the notes field.",
    )
    update_parser.set_defaults(func=App.cmd_update)

    delete_parser = subparsers.add_parser(
        "delete",
        aliases=["rm", "remove"],
        help="Delete a word.",
    )
    delete_parser.add_argument(
        "target",
        metavar="TARGET",
        help="Entry ID, word, gloss, or unique partial match.",
    )
    delete_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    delete_parser.set_defaults(func=App.cmd_delete)

    search_parser = subparsers.add_parser(
        "search",
        aliases=["find"],
        help="Search words, meanings, and notes.",
    )
    search_parser.add_argument(
        "query",
        metavar="QUERY",
        help="Text to find in a word, English/中文 meaning, or notes.",
    )
    search_parser.set_defaults(func=App.cmd_search)

    stats_parser = subparsers.add_parser(
        "stats",
        aliases=["statistics"],
        help="Show character and daily-contribution statistics.",
    )
    stats_parser.add_argument(
        "--days",
        type=int,
        default=30,
        metavar="N",
        help="Number of recent UTC days to chart (1-366; default: 30).",
    )
    stats_parser.add_argument(
        "--top",
        type=int,
        default=20,
        metavar="N",
        help="Number of character-frequency rows to show (1-100; default: 20).",
    )
    stats_parser.set_defaults(func=App.cmd_stats)

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    console = Console(False if args.no_color else None)
    data_path = resolve_data_path(args.data_file)
    try:
        lexicon = Lexicon.load(data_path)
    except LexiconError as exc:
        console.error(str(exc))
        return 1

    app = App(lexicon, console)
    handler = getattr(args, "func", None)
    if handler is None:
        try:
            return app.run_menu()
        except BrokenPipeError:
            return 0
        except KeyboardInterrupt:
            console.blank()
            console.hint("Cancelled.")
            return 130

    try:
        result = handler(app, args)
        return int(result or 0)
    except CliUsageError as exc:
        console.error(str(exc))
        return 2
    except PromptCancelled:
        console.blank()
        console.hint("Cancelled.")
        return 130
    except EndOfInput:
        console.blank()
        console.hint("Cancelled (end of input).")
        return 1
    except LexiconError as exc:
        app.report_error(exc)
        return 1
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        console.blank()
        console.hint("Cancelled.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
