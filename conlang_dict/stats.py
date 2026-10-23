"""Dictionary statistics: character frequency and creation activity."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from .dictionary import Entry


@dataclass(frozen=True, slots=True)
class DayContribution:
    day: date
    count: int


@dataclass(frozen=True, slots=True)
class DictionaryStats:
    entries: int
    distinct_meanings: int
    total_characters: int
    unique_characters: int
    average_word_length: float
    longest_word: str
    longest_word_length: int
    first_created: date | None
    latest_created: date | None
    active_days: int
    current_streak: int
    longest_streak: int
    most_productive_day: date | None
    most_productive_count: int


def character_frequencies(entries: tuple[Entry, ...]) -> Counter[str]:
    """Count constructed-language characters, ignoring capitalization."""

    counts: Counter[str] = Counter()
    for entry in entries:
        counts.update(entry.word.casefold())
    return counts


def creation_date(entry: Entry) -> date | None:
    try:
        parsed = datetime.fromisoformat(entry.created_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date()


def contributions_by_day(
    entries: tuple[Entry, ...],
    days: int,
    *,
    today: date | None = None,
) -> tuple[DayContribution, ...]:
    """Return one contribution count for each of the last ``days`` days."""

    if days < 1:
        raise ValueError("days must be at least 1")
    end = today or datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    counts = Counter(
        created
        for entry in entries
        if (created := creation_date(entry)) is not None
        and start <= created <= end
    )
    return tuple(
        DayContribution(
            day=start + timedelta(days=offset),
            count=counts[start + timedelta(days=offset)],
        )
        for offset in range(days)
    )


def summarize(
    entries: tuple[Entry, ...],
    *,
    today: date | None = None,
) -> DictionaryStats:
    frequencies = character_frequencies(entries)
    lengths = [len(entry.word) for entry in entries]
    longest_word = ""
    if entries:
        longest_word = min(
            (entry.word for entry in entries if len(entry.word) == max(lengths)),
            key=str.casefold,
        )

    dates = [
        created
        for entry in entries
        if (created := creation_date(entry)) is not None
    ]
    unique_dates = sorted(set(dates))
    active_days = len(unique_dates)
    current = _current_streak(unique_dates, today or datetime.now(timezone.utc).date())
    longest = _longest_streak(unique_dates)

    day_counts = Counter(dates)
    most_productive_day: date | None = None
    most_productive_count = 0
    if day_counts:
        most_productive_day, most_productive_count = min(
            day_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )

    meanings = {
        (entry.english.casefold(), entry.chinese.casefold())
        for entry in entries
    }
    total_characters = sum(lengths)
    average = (total_characters / len(entries)) if entries else 0.0

    return DictionaryStats(
        entries=len(entries),
        distinct_meanings=len(meanings),
        total_characters=total_characters,
        unique_characters=len(frequencies),
        average_word_length=average,
        longest_word=longest_word,
        longest_word_length=max(lengths, default=0),
        first_created=min(unique_dates) if unique_dates else None,
        latest_created=max(unique_dates) if unique_dates else None,
        active_days=active_days,
        current_streak=current,
        longest_streak=longest,
        most_productive_day=most_productive_day,
        most_productive_count=most_productive_count,
    )


def _current_streak(days: list[date], today: date) -> int:
    unique = set(days)
    cursor = today if today in unique else today - timedelta(days=1)
    streak = 0
    while cursor in unique:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _longest_streak(days: list[date]) -> int:
    if not days:
        return 0
    longest = 1
    current = 1
    previous = days[0]
    for day in days[1:]:
        if day == previous + timedelta(days=1):
            current += 1
            longest = max(longest, current)
        elif day != previous:
            current = 1
        previous = day
    return longest
