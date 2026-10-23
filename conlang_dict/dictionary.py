"""Lexicon model, validation, duplicate checks, and JSON persistence."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .similarity import is_similar, similarity_score

FORMAT_NAME = "conlang-lexicon"
FORMAT_VERSION = 1
MAX_WORD_LENGTH = 64
MAX_MEANING_LENGTH = 120
MAX_NOTES_LENGTH = 2000

_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")


class LexiconError(Exception):
    """Base class for expected, user-facing dictionary problems."""


class ValidationError(LexiconError):
    """A word or meaning failed validation."""


class DuplicateWordError(LexiconError):
    """The constructed word is already used by another entry."""

    def __init__(self, word: str, existing: "Entry") -> None:
        self.word = word
        self.existing = existing
        super().__init__(
            f'"{word}" is already in the dictionary as #{existing.id}: '
            f"{existing.english} — {existing.chinese}."
        )


class EntryNotFoundError(LexiconError):
    """A lookup did not resolve to an entry."""

    def __init__(self, query: str) -> None:
        self.query = query
        super().__init__(f'No entry matches "{query}".')


class AmbiguousEntryError(LexiconError):
    """A lookup matched several entries."""

    def __init__(self, query: str, matches: tuple["Entry", ...]) -> None:
        self.query = query
        self.matches = matches
        super().__init__(f'"{query}" matches {len(matches)} entries.')


class LexiconFileError(LexiconError):
    """The dictionary file could not be read or written."""


def utc_now() -> str:
    """Return a compact UTC ISO-8601 timestamp."""

    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def validate_word(raw: object) -> str:
    """Validate and return an ASCII constructed-language word.

    The spelling may contain letters plus internal hyphens or apostrophes.
    Uniqueness is checked separately because it depends on existing entries.
    """

    if not isinstance(raw, str):
        raise ValidationError("Word must be text.")
    word = raw.strip()
    if not word:
        raise ValidationError("Word cannot be empty.")
    if len(word) > MAX_WORD_LENGTH:
        raise ValidationError(
            f"Word must be at most {MAX_WORD_LENGTH} characters long."
        )
    if not word.isascii():
        raise ValidationError(
            "Word must use ASCII characters only; accented or non-Latin "
            "letters are not allowed."
        )
    if not _WORD_PATTERN.fullmatch(word):
        raise ValidationError(
            "Use ASCII letters, with optional internal hyphens (-) or "
            "apostrophes ('). Spaces, digits, and leading/trailing punctuation "
            "are not allowed."
        )
    return word


def clean_meaning(raw: object, label: str = "Meaning") -> str:
    """Normalize an English or Chinese gloss."""

    if not isinstance(raw, str):
        raise ValidationError(f"{label} must be text.")
    text = " ".join(raw.split())
    if not text:
        raise ValidationError(f"{label} cannot be empty.")
    if len(text) > MAX_MEANING_LENGTH:
        raise ValidationError(
            f"{label} must be at most {MAX_MEANING_LENGTH} characters long."
        )
    if any(unicodedata.category(char).startswith("C") for char in text):
        raise ValidationError(f"{label} contains an unsupported control character.")
    return text


def clean_notes(raw: object) -> str:
    """Normalize optional free-form notes to a single line."""

    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise ValidationError("Notes must be text.")
    text = " ".join(raw.split())
    if len(text) > MAX_NOTES_LENGTH:
        raise ValidationError(
            f"Notes must be at most {MAX_NOTES_LENGTH} characters long."
        )
    if any(unicodedata.category(char).startswith("C") for char in text):
        raise ValidationError("Notes contain an unsupported control character.")
    return text


def _validate_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty timestamp string.")
    return value


@dataclass(frozen=True, slots=True)
class Entry:
    """One constructed word and its natural-language mapping."""

    id: int
    word: str
    english: str
    chinese: str
    notes: str
    created_at: str
    updated_at: str

    @property
    def word_key(self) -> str:
        return self.word.casefold()

    @property
    def pair(self) -> str:
        return f"{self.english} — {self.chinese}"

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "word": self.word,
            "english": self.english,
            "chinese": self.chinese,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: object, index: int) -> "Entry":
        if not isinstance(payload, dict):
            raise ValidationError("entry must be a JSON object.")

        entry_id = payload.get("id")
        if isinstance(entry_id, bool) or not isinstance(entry_id, int) or entry_id < 1:
            raise ValidationError("id must be a positive integer.")

        try:
            word = validate_word(payload.get("word"))
            english = clean_meaning(payload.get("english"), "English meaning")
            chinese = clean_meaning(payload.get("chinese"), "Chinese meaning")
            notes = clean_notes(payload.get("notes", ""))
            created_at = _validate_timestamp(payload.get("created_at"), "created_at")
            updated_at = _validate_timestamp(payload.get("updated_at"), "updated_at")
        except ValidationError as exc:
            raise ValidationError(f"entry #{index}: {exc}") from exc

        return cls(
            id=entry_id,
            word=word,
            english=english,
            chinese=chinese,
            notes=notes,
            created_at=created_at,
            updated_at=updated_at,
        )


@dataclass(frozen=True, slots=True)
class WordSuggestion:
    """An existing word that looks similar to a proposed spelling."""

    entry: Entry
    distance: int
    ratio: float


class Lexicon:
    """A persistent collection of constructed-language entries."""

    def __init__(
        self,
        path: str | Path,
        entries: Iterable[Entry] = (),
        next_id: int | None = None,
    ) -> None:
        self.path = Path(path)
        self._entries: dict[int, Entry] = {}
        for entry in entries:
            if entry.id in self._entries:
                raise LexiconFileError(f"Duplicate entry id #{entry.id}.")
            self._entries[entry.id] = entry

        max_id = max(self._entries, default=0)
        requested_next = next_id if next_id is not None else 1
        if isinstance(requested_next, bool) or not isinstance(requested_next, int):
            raise LexiconFileError("next_id must be a positive integer.")
        self._next_id = max(requested_next, max_id + 1, 1)
        self._check_unique_words()

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> tuple[Entry, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))

    def get(self, entry_id: int) -> Entry:
        try:
            return self._entries[entry_id]
        except KeyError as exc:
            raise EntryNotFoundError(str(entry_id)) from exc

    def duplicate_of(self, word: str, *, exclude_id: int | None = None) -> Entry | None:
        """Return the entry using ``word`` case-insensitively, if any."""

        key = word.casefold()
        for entry in self.entries:
            if entry.id == exclude_id:
                continue
            if entry.word_key == key:
                return entry
        return None

    def entries_for_english(self, english: str) -> tuple[Entry, ...]:
        """Return all entries mapped to an English meaning."""

        key = english.casefold()
        return tuple(
            entry for entry in self.entries if entry.english.casefold() == key
        )

    def mapped_english_keys(self) -> frozenset[str]:
        """Return the lowercase English meanings already represented."""

        return frozenset(entry.english.casefold() for entry in self.entries)

    def similar_words(
        self,
        word: str,
        *,
        exclude_id: int | None = None,
        limit: int = 5,
    ) -> tuple[WordSuggestion, ...]:
        """Return existing spellings that are close to ``word``."""

        needle = word.strip()
        if not needle or limit < 1:
            return ()

        suggestions: list[WordSuggestion] = []
        for entry in self.entries:
            if entry.id == exclude_id:
                continue
            if not is_similar(needle, entry.word):
                continue
            distance, ratio = similarity_score(needle, entry.word)
            suggestions.append(
                WordSuggestion(entry=entry, distance=distance, ratio=ratio)
            )

        suggestions.sort(
            key=lambda item: (
                item.distance,
                -item.ratio,
                item.entry.word.casefold(),
                item.entry.id,
            )
        )
        return tuple(suggestions[:limit])

    def resolve(self, query: str) -> Entry:
        """Resolve an ID, exact spelling, gloss, or unique partial match."""

        query = query.strip()
        if not query:
            raise EntryNotFoundError(query)

        if query.isdigit():
            entry = self._entries.get(int(query))
            if entry is not None:
                return entry

        needle = query.casefold()
        word_matches = [
            entry for entry in self.entries if entry.word.casefold() == needle
        ]
        if len(word_matches) == 1:
            return word_matches[0]

        english_matches = [
            entry for entry in self.entries if entry.english.casefold() == needle
        ]
        if len(english_matches) == 1:
            return english_matches[0]

        chinese_matches = [
            entry for entry in self.entries if entry.chinese.casefold() == needle
        ]
        if len(chinese_matches) == 1:
            return chinese_matches[0]

        partial = [
            entry
            for entry in self.entries
            if needle in entry.word.casefold()
            or needle in entry.english.casefold()
            or needle in entry.chinese.casefold()
        ]
        unique_partial = {entry.id: entry for entry in partial}.values()
        ordered = tuple(sorted(unique_partial, key=lambda entry: entry.id))
        if len(ordered) == 1:
            return ordered[0]
        if len(ordered) > 1:
            raise AmbiguousEntryError(query, ordered)
        raise EntryNotFoundError(query)

    def search(self, query: str) -> tuple[Entry, ...]:
        """Search every searchable field using a case-insensitive substring."""

        needle = query.strip().casefold()
        if not needle:
            return ()
        matches = [
            entry
            for entry in self.entries
            if needle in entry.word.casefold()
            or needle in entry.english.casefold()
            or needle in entry.chinese.casefold()
            or needle in entry.notes.casefold()
        ]
        return tuple(sorted(matches, key=lambda entry: (entry.word.casefold(), entry.id)))

    def add(
        self,
        word: str,
        english: str,
        chinese: str,
        notes: str = "",
    ) -> Entry:
        """Validate, persist, and return a new entry."""

        clean_word = validate_word(word)
        clean_english = clean_meaning(english, "English meaning")
        clean_chinese = clean_meaning(chinese, "Chinese meaning")
        cleaned_notes = clean_notes(notes)

        existing = self.duplicate_of(clean_word)
        if existing is not None:
            raise DuplicateWordError(clean_word, existing)

        now = utc_now()
        entry = Entry(
            id=self._next_id,
            word=clean_word,
            english=clean_english,
            chinese=clean_chinese,
            notes=cleaned_notes,
            created_at=now,
            updated_at=now,
        )
        self._entries[entry.id] = entry
        self._next_id += 1
        try:
            self.save()
        except Exception:
            del self._entries[entry.id]
            self._next_id -= 1
            raise
        return entry

    def update(
        self,
        entry_id: int,
        *,
        word: str | None = None,
        english: str | None = None,
        chinese: str | None = None,
        notes: str | None = None,
    ) -> Entry:
        """Update selected fields and persist the result.

        ``None`` means "leave unchanged".  Supplying an empty notes string
        clears the notes field.
        """

        current = self.get(entry_id)
        changes: dict[str, str] = {}

        if word is not None:
            clean_word = validate_word(word)
            if clean_word != current.word:
                duplicate = self.duplicate_of(clean_word, exclude_id=entry_id)
                if duplicate is not None:
                    raise DuplicateWordError(clean_word, duplicate)
                changes["word"] = clean_word

        if english is not None:
            clean_english = clean_meaning(english, "English meaning")
            if clean_english != current.english:
                changes["english"] = clean_english

        if chinese is not None:
            clean_chinese = clean_meaning(chinese, "Chinese meaning")
            if clean_chinese != current.chinese:
                changes["chinese"] = clean_chinese

        if notes is not None:
            clean_notes_value = clean_notes(notes)
            if clean_notes_value != current.notes:
                changes["notes"] = clean_notes_value

        if not changes:
            return current

        updated = replace(current, **changes, updated_at=utc_now())
        self._entries[entry_id] = updated
        try:
            self.save()
        except Exception:
            self._entries[entry_id] = current
            raise
        return updated

    def delete(self, entry_id: int) -> Entry:
        """Delete an entry and persist the result."""

        entry = self.get(entry_id)
        del self._entries[entry_id]
        try:
            self.save()
        except Exception:
            self._entries[entry_id] = entry
            raise
        return entry

    def save(self) -> None:
        """Atomically write the lexicon as UTF-8 JSON."""

        payload = {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "next_id": self._next_id,
            "entries": [entry.to_dict() for entry in self.entries],
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

        temp_name: str | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temp_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=str(self.path.parent),
            )
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
            temp_name = None
        except OSError as exc:
            message = exc.strerror or str(exc)
            raise LexiconFileError(
                f'Could not save dictionary to "{self.path}": {message}'
            ) from exc
        finally:
            if temp_name is not None:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass

    @classmethod
    def load(cls, path: str | Path) -> "Lexicon":
        """Load a lexicon, returning an empty one when the file is absent."""

        path = Path(path)
        if not path.exists():
            return cls(path)

        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise LexiconFileError(
                f'Dictionary file "{path}" is not valid UTF-8.'
            ) from exc
        except OSError as exc:
            raise LexiconFileError(
                f'Could not read dictionary file "{path}": '
                f"{exc.strerror or exc}"
            ) from exc

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LexiconFileError(
                f'Dictionary file "{path}" is not valid JSON '
                f"(line {exc.lineno}, column {exc.colno})."
            ) from exc

        if not isinstance(payload, dict):
            raise LexiconFileError(
                f'Dictionary file "{path}" must contain a JSON object.'
            )
        if payload.get("format") != FORMAT_NAME:
            raise LexiconFileError(
                f'"{path}" does not look like a {FORMAT_NAME} dictionary file.'
            )
        if payload.get("version") != FORMAT_VERSION:
            raise LexiconFileError(
                f'Dictionary file "{path}" uses unsupported format version '
                f"{payload.get('version')!r}; expected {FORMAT_VERSION}."
            )

        raw_entries = payload.get("entries")
        if not isinstance(raw_entries, list):
            raise LexiconFileError(
                f'Dictionary file "{path}" is missing an entries list.'
            )

        entries: list[Entry] = []
        seen_ids: set[int] = set()
        for index, raw_entry in enumerate(raw_entries, start=1):
            try:
                entry = Entry.from_dict(raw_entry, index)
            except ValidationError as exc:
                raise LexiconFileError(
                    f'Invalid entry in dictionary file "{path}": {exc}'
                ) from exc
            if entry.id in seen_ids:
                raise LexiconFileError(
                    f'Invalid dictionary file "{path}": duplicate entry id '
                    f"#{entry.id}."
                )
            seen_ids.add(entry.id)
            entries.append(entry)

        by_word: dict[str, Entry] = {}
        for entry in entries:
            if entry.word_key in by_word:
                raise LexiconFileError(
                    f'Invalid dictionary file "{path}": words '
                    f'"{by_word[entry.word_key].word}" and "{entry.word}" '
                    "are duplicates (word uniqueness is case-insensitive)."
                )
            by_word[entry.word_key] = entry

        raw_next = payload.get("next_id", max(seen_ids, default=0) + 1)
        if isinstance(raw_next, bool) or not isinstance(raw_next, int) or raw_next < 1:
            raise LexiconFileError(
                f'Invalid dictionary file "{path}": next_id must be a '
                "positive integer."
            )

        return cls(path, entries, raw_next)

    def _check_unique_words(self) -> None:
        seen: dict[str, Entry] = {}
        for entry in self.entries:
            key = entry.word_key
            if key in seen:
                raise LexiconFileError(
                    f'Duplicate words "{seen[key].word}" and "{entry.word}".'
                )
            seen[key] = entry
