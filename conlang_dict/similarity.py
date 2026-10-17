"""Spelling comparison helpers used for near-duplicate detection."""

from __future__ import annotations

from difflib import SequenceMatcher


def damerau_levenshtein(left: str, right: str) -> int:
    """Return the optimal-string-alignment distance between two strings.

    Insertions, deletions, substitutions, and adjacent transpositions each cost
    one edit.  This is a better fit than plain Levenshtein for typed words,
    where ``shae`` / ``seha`` is a common slip.
    """

    left = left.casefold()
    right = right.casefold()
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    # Rows/columns are offset by one to represent the empty prefix.
    distance = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    for i in range(len(left) + 1):
        distance[i][0] = i
    for j in range(len(right) + 1):
        distance[0][j] = j

    for i in range(1, len(left) + 1):
        for j in range(1, len(right) + 1):
            cost = 0 if left[i - 1] == right[j - 1] else 1
            distance[i][j] = min(
                distance[i - 1][j] + 1,      # delete
                distance[i][j - 1] + 1,      # insert
                distance[i - 1][j - 1] + cost,  # substitute / match
            )
            if (
                i > 1
                and j > 1
                and left[i - 1] == right[j - 2]
                and left[i - 2] == right[j - 1]
            ):
                distance[i][j] = min(
                    distance[i][j],
                    distance[i - 2][j - 2] + 1,  # adjacent transposition
                )

    return distance[-1][-1]


def similarity_ratio(left: str, right: str) -> float:
    """Return a 0..1 similarity ratio for two spellings."""

    return SequenceMatcher(
        None, left.casefold(), right.casefold(), autojunk=False
    ).ratio()


def similarity_score(word: str, candidate: str) -> tuple[int, float]:
    """Return ``(edit_distance, ratio)`` for two spellings."""

    word = word.casefold()
    candidate = candidate.casefold()
    return damerau_levenshtein(word, candidate), similarity_ratio(word, candidate)


def is_similar(word: str, candidate: str) -> bool:
    """Decide whether ``candidate`` is worth showing as a spelling hint.

    The edit-distance allowance grows a little with word length, but is capped
    at three.  A ratio floor prevents tiny words from matching unrelated
    spellings that happen to be one edit apart.
    """

    word = word.casefold()
    candidate = candidate.casefold()
    if not word or not candidate or word == candidate:
        return False

    distance, ratio = similarity_score(word, candidate)
    allowance = max(1, min(3, (len(word) + 2) // 3))
    return distance <= allowance and ratio >= 0.55
