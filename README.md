# Conlang Lexicon

A dependency-free Python CLI for building a dictionary of an artificial
language. Every constructed word is mapped to an **English — 中文** meaning,
stored in a small JSON file, and checked for duplicate or confusingly similar
spellings.

The app is designed for conlangers who want a quick, local lexicon without a
database or a GUI.

## Highlights

- Guided word creation using a catalog of **2,811 English–Chinese meanings**:
  six curated topical groups plus 2,809 NGSL headwords.
- Already-mapped meanings are hidden from the picker by default; a toggle shows
  them when you deliberately want to create a synonym.
- Basic CRUD: create, list/show/search, update, and delete.
- Statistics view: character frequency, average/longest word, activity streaks,
  and a daily contribution chart.
- Persistent, human-readable JSON storage with atomic writes.
- ASCII-only word validation.
- Case-insensitive duplicate rejection (`vela`, `Vela`, and `VELA` are the same
  word).
- Similar-spelling hints, both before creation (with an optional confirmation)
  and after every successful creation.
- Interactive menu when run without a command, plus scriptable subcommands.
- English and Chinese text, with terminal-width-aware tables and pagination.

## Requirements

- Python 3.10 or newer.
- No third-party packages at runtime.

## Quick start

From this project directory:

```console
$ python -m conlang_dict
```

Or install the `conlang-dict` command:

```console
$ python -m pip install -e .
$ conlang-dict
```

The first write creates `data/dictionary.json` under the current working
directory. Choose a different file with the global `--file` option or the
`CONLANG_DICT_FILE` environment variable:

```console
$ python -m conlang_dict --file my-language.json create
$ CONLANG_DICT_FILE=my-language.json python -m conlang_dict list
```

On PowerShell, set the environment variable separately:

```powershell
$env:CONLANG_DICT_FILE = "my-language.json"
python -m conlang_dict list
```

> Global options such as `--file` go **before** the subcommand.

## Creating a word

`create` is guided by default:

```console
$ python -m conlang_dict create

  Create a new word
  ─────────────────
  Choose an English — 中文 meaning, then invent an ASCII spelling.

  Choose a meaning (English — 中文)
     1  People & pronouns (9)
     2  Nature (14, 1 mapped)
     3  Body & animals (7)
     4  Actions (12)
     5  Qualities & time (10)
     6  Numbers & quantity (5)
     7  General vocabulary A–Z (2754)
     s  Search all meanings
     c  Custom English — 中文 pair
     m  Show already-mapped meanings
     b  Cancel
  Already-mapped meanings are hidden by default.

? Choose [1-7/s/c/m/b]: s
? Search English, 中文, or category: fire
  Found: fire — 火  (Nature)

  Selected meaning: fire — 火
  Definition: heat and the flame produced when burning
? New word (ASCII letters, optional internal - or '): velar

  ✓ Added "velar" (#2): fire — 火
  Similar existing spellings: "vela" (#1).
```

If an existing word is spelled similarly, the app shows the candidates and
asks whether to continue:

```console
  Similar existing spellings
    • vela (#1) — water — 水  (distance 1)

? Create "velar" anyway? [Y/n]:
```

After the entry is saved, its similar existing words are reported again as a
final hint.

### Choosing a meaning

The catalog is larger than the terminal menu can comfortably display, so there
are several ways to find a meaning:

- **Curated categories** — people, nature, body/animals, actions, qualities,
  and numbers.
- **General vocabulary A–Z** — browse the NGSL headwords by first letter. Lists
  are paginated with `n` (next) and `p` (previous).
- **Search all meanings** — search by English, 中文, or category. Exact English
  matches rank first, followed by prefix/substring and Chinese matches.
- **Custom English — 中文 pair** — enter any meaning not in the catalog.

A meaning that already has a constructed word is **hidden by default**, so the
same concept is not offered again accidentally. Press `m` to show those
meanings with a `✓ already mapped` marker. Selecting one asks for confirmation
before creating a synonym. Guided creation therefore never creates a second
entry for the same English meaning silently.

`Definition:` lines come from the NGSL workbook and appear after a meaning is
chosen.

### Spelling rules

A constructed word must:

- be 1–64 characters long;
- use ASCII letters (`A–Z`, `a–z`);
- optionally contain **internal** hyphens or apostrophes, as in
  `tlhIngan-Hol` or `o'neil`;
- not contain spaces, digits, leading/trailing punctuation, or consecutive
  punctuation;
- be unique ignoring capitalization. Original capitalization is preserved for
  display.

Two different words may share the same English–Chinese meaning; the app calls
these synonyms. The duplicate rule applies to the constructed spelling, not to
the meaning. Synonyms are available through the mapped-meaning toggle or a
custom meaning.

### Similar-spelling hints

Hints use the Damerau–Levenshtein edit distance (adjacent transpositions count
as one edit) plus a string-similarity ratio. Up to five suggestions are shown,
ordered by distance. The edit-distance allowance grows slightly with word
length but is capped at three edits. This keeps short words from producing
noisy hints while still catching common typos.

## Commands

```text
conlang-dict [--file PATH] [--no-color] COMMAND ...
```

| Command | What it does |
| --- | --- |
| `create` / `add` / `new` | Guided create. |
| `list` / `ls` | List all entries; sort with `--sort` (`word`, `id`, `english`, or `chinese`). |
| `show` / `lookup TARGET` | Show one entry's details. |
| `update` / `edit TARGET` | Edit fields, prompting for each value. |
| `delete` / `rm TARGET` | Delete after confirmation. |
| `search` / `find QUERY` | Search words, meanings, and notes. |
| `stats` / `statistics` | Show character frequency and daily contributions. |
| *(no command)* | Open the interactive menu. |

`TARGET` may be an entry ID, exact constructed word (case-insensitive), exact
English or Chinese gloss, or a unique partial match. Ambiguous targets list the
candidate IDs.

### Quick, non-interactive create

Supplying `--word`, `--english`, and `--chinese` together skips the prompts:

```console
$ python -m conlang_dict create --word vela --english water --chinese 水 --notes "river word"
```

This bypasses the mapped-meaning guard because the meaning is explicit.

Other examples:

```console
$ python -m conlang_dict list
$ python -m conlang_dict show vela
$ python -m conlang_dict search 水
$ python -m conlang_dict update vela --english sea --chinese 海
$ python -m conlang_dict update vela --clear-notes
$ python -m conlang_dict stats
$ python -m conlang_dict delete vela --yes
```

For guided updates, press Enter to keep the current value. Notes can be cleared
by entering `-` at the notes prompt, or non-interactively with `--clear-notes`.

## Statistics

`stats` summarizes the entire dictionary:

```console
$ python -m conlang_dict stats
```

It shows:

- entry count and distinct meanings;
- total and unique characters, average word length, longest word;
- first/latest entry date, active days, current and longest creation streaks;
- the most productive day;
- character frequency, ignoring capitalization, with counts and shares;
- a per-day contribution table for recent UTC days, with bars and a total.

Options:

```console
$ python -m conlang_dict stats --days 90 --top 30
```

- `--days N` controls the daily-contribution window (1–366; default 30).
- `--top N` controls how many character-frequency rows are shown (1–100;
  default 20).

Contribution counts words **created** on each day, based on `created_at`.
Updates are not counted as new contributions. The same report is available as
menu option 7.

## Interactive menu

Running without a command opens:

```text
  Conlang Lexicon
  A dictionary builder for invented languages
  ──────────────────────────────────────────────
  data/dictionary.json  ·  3 words

   1  Create a word
   2  List words
   3  Show a word
   4  Update a word
   5  Delete a word
   6  Search
   7  Statistics
   8  Quit
```

## Data file

The file is UTF-8 JSON and is written atomically (a temporary file in the same
directory is renamed over the old one), so an interrupted write should not
leave a half-written dictionary.

```json
{
  "format": "conlang-lexicon",
  "version": 1,
  "next_id": 2,
  "entries": [
    {
      "id": 1,
      "word": "vela",
      "english": "water",
      "chinese": "水",
      "notes": "",
      "created_at": "2026-10-17T12:00:00Z",
      "updated_at": "2026-10-17T12:00:00Z"
    }
  ]
}
```

Entry IDs are stable and are not reused after deletion. Timestamps are UTC.
Malformed files, duplicate IDs/words, invalid entries, and unsupported format
versions produce a clear error instead of being silently overwritten.

## Project layout

```text
conlang-dictionary/
├── conlang_dict/
│   ├── __init__.py
│   ├── __main__.py       # python -m conlang_dict
│   ├── cli.py            # commands, prompts, session flows
│   ├── concepts.py       # catalog loader and search
│   ├── dictionary.py     # model, validation, JSON persistence
│   ├── display.py        # terminal styling and tables
│   ├── similarity.py     # edit distance and spelling hints
│   ├── stats.py          # character and daily-activity metrics
│   └── data/
│       └── concepts.json # 2,811 English–Chinese meanings
├── tests/
│   ├── test_cli.py
│   ├── test_concepts.py
│   ├── test_dictionary.py
│   ├── test_similarity.py
│   └── test_stats.py
├── THIRD_PARTY_NOTICES.md
├── pyproject.toml
└── README.md
```

## Tests

```console
$ python -m unittest discover -s tests -v
```

The suite covers validation, duplicate handling, CRUD persistence, file-format
errors, edit distance, similarity ranking, the expanded catalog and map
filtering, statistics, guided creation, and the CLI commands.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success, or a cancelled action. |
| `1` | Validation, duplicate, missing entry, or dictionary-file error. |
| `2` | Invalid command-line usage. |
| `130` | Interrupted with Ctrl+C. |

## Data sources

- English headwords and definitions: **NGSL 1.2** (New General Service List),
  from the workbook supplied for this project. See
  <https://www.newgeneralservicelist.com/>.
- Chinese glosses: derived from **ECDICT**, MIT licensed. See
  <https://github.com/skywind3000/ECDICT>.

The full attribution and ECDICT license text are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Notes and limitations

- The app is a single-user local tool; simultaneous writers are not coordinated.
- Similarity hints are advisory. Only exact case-insensitive spelling matches
  are rejected.
- The mapped-meaning guard compares the English headword, case-insensitively.
  Two entries with different English glosses are considered different meanings.
- Daily contributions use `created_at`; historical update activity is not
  recorded.
- `NO_COLOR=1` or `--no-color` disables ANSI styling. Colour is also disabled
  automatically when output is redirected.
