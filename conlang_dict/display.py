"""Terminal presentation helpers with no third-party dependencies."""

from __future__ import annotations

import os
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"


def configure_stdio() -> None:
    """Use UTF-8 for piped input and output (important on Windows)."""

    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (LookupError, OSError):
            pass


def _enable_windows_ansi() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        # Colour is cosmetic; never fail because the console rejects VT mode.
        pass


def _cell_width(char: str) -> int:
    if unicodedata.combining(char):
        return 0
    if unicodedata.category(char) in {"Cc", "Cf"}:
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def display_width(text: str) -> int:
    """Approximate the terminal-cell width of text, including CJK characters."""

    return sum(_cell_width(char) for char in text)


def truncate_display(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text
    if width == 1:
        return "…"
    result: list[str] = []
    used = 0
    for char in text:
        char_width = _cell_width(char)
        if used + char_width > width - 1:
            break
        result.append(char)
        used += char_width
    return "".join(result) + "…"


def pad_display(text: str, width: int, *, right: bool = False) -> str:
    clipped = truncate_display(text, width)
    padding = max(0, width - display_width(clipped))
    if right:
        return " " * padding + clipped
    return clipped + " " * padding


def format_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError):
        return value


def display_path(path: Path) -> str:
    """Prefer a path relative to the current directory when possible."""

    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except (ValueError, OSError):
        return str(path)


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    return singular if count == 1 else (plural_form or singular + "s")


class Console:
    """Small styled-output facade used by the CLI."""

    def __init__(self, color: bool | None = None) -> None:
        requested = True if color is None else color
        enabled = (
            requested
            and sys.stdout.isatty()
            and "NO_COLOR" not in os.environ
            and os.environ.get("TERM", "") != "dumb"
        )
        self.color = bool(enabled)
        if self.color:
            _enable_windows_ansi()

    def style(self, text: str, *codes: str) -> str:
        if not self.color or not codes:
            return text
        return "".join(codes) + text + RESET

    def bold(self, text: str) -> str:
        return self.style(text, BOLD)

    def dim(self, text: str) -> str:
        return self.style(text, DIM)

    def cyan(self, text: str) -> str:
        return self.style(text, CYAN)

    def green(self, text: str) -> str:
        return self.style(text, GREEN)

    def yellow(self, text: str) -> str:
        return self.style(text, YELLOW)

    def red(self, text: str) -> str:
        return self.style(text, RED)

    def print(self, *values: object, **kwargs: object) -> None:
        print(*values, **kwargs)

    def blank(self) -> None:
        print()

    def heading(self, text: str) -> None:
        print()
        print("  " + self.bold(self.cyan(text)))
        print("  " + self.dim("─" * min(display_width(text), 58)))

    def section(self, text: str) -> None:
        print()
        print("  " + self.bold(text))

    def success(self, text: str) -> None:
        print("  " + self.green("✓ " + text))

    def warning(self, text: str) -> None:
        print("  " + self.yellow("! " + text))

    def error(self, text: str) -> None:
        print("  " + self.red("✗ " + text))

    def info(self, text: str) -> None:
        print("  " + self.cyan("• " + text))

    def hint(self, text: str) -> None:
        print("  " + self.dim(text))

    def print_table(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[str]],
        *,
        caps: Sequence[int] = (4, 22, 28, 18),
        right_columns: Sequence[int] = (0,),
    ) -> None:
        print()
        for line in render_table(
            headers, rows, caps=caps, right_columns=right_columns
        ):
            print("  " + line)
        print()


def render_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    caps: Sequence[int] = (4, 22, 28, 18),
    right_columns: Sequence[int] = (0,),
) -> list[str]:
    """Render an aligned Unicode table, adapting to the terminal width."""

    column_count = len(headers)
    if any(len(row) != column_count for row in rows):
        raise ValueError("Every table row must have the same number of cells.")
    if len(caps) != column_count:
        raise ValueError("Provide one width cap per table column.")

    widths: list[int] = []
    for index, header in enumerate(headers):
        content_width = max(
            [display_width(header)]
            + [display_width(str(row[index])) for row in rows]
        )
        widths.append(min(content_width, caps[index]))

    minimums = [
        min(max(display_width(header), 1), caps[index])
        for index, header in enumerate(headers)
    ]
    available = max(38, shutil.get_terminal_size(fallback=(90, 24)).columns - 2)
    separator_width = 2 * (column_count - 1)
    while sum(widths) + separator_width > available:
        shrinkable = [
            index
            for index in range(column_count)
            if widths[index] > minimums[index]
        ]
        if not shrinkable:
            break
        widest = max(shrinkable, key=lambda index: widths[index])
        widths[widest] -= 1

    def make_row(values: Sequence[object]) -> str:
        cells = []
        for index, value in enumerate(values):
            cells.append(
                pad_display(
                    str(value),
                    widths[index],
                    right=index in right_columns,
                )
            )
        return "  ".join(cells).rstrip()

    header_line = make_row([header.upper() for header in headers])
    separator = "  ".join("─" * width for width in widths)
    rendered = [header_line, separator]
    rendered.extend(make_row(row) for row in rows)
    return rendered
