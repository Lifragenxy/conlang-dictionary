# Conlang Lexicon

A dependency-free Python CLI for building a dictionary of an artificial
language. Every constructed word is mapped to an **English — 中文** meaning,
stored in a small JSON file, and checked for duplicate or confusingly similar
spellings.

The app is designed for conlangers who want a quick, local lexicon without a
database or a GUI.

## Highlights

- Guided word creation that shows English–Chinese meanings and asks for the
  invented spelling.
- Basic CRUD: create, list/show/search, update, and delete.
- Persistent, human-readable JSON storage with atomic writes.
- ASCII-only word validation.
- Case-insensitive duplicate rejection (`vela`, `Vela`, and `VELA` are the same
  word).
- Similar-spelling hints, both before creation (with an optional confirmation)
  and after every successful creation.
- Optional synonyms: different constructed words may map to the same meaning.
- Interactive menu when run without a command, plus scriptable subcommands.
- English and Chinese text, with terminal-width-aware tables.

## Requirements

- Python 3.10 or newer.
- No third-party packages.

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
     2  Nature (14)
     3  Body & animals (7)
     4  Actions (12)
     5  Qualities & time (10)
     6  Numbers & quantity (5)
     s  Search all meanings
     c  Custom English — 中文 pair
     b  Cancel

? Choose [1-6/s/c/b]: s
? Search English, 中文, or category: water
  Found: water — 水  (Nature)

  Selected meaning: water — 水
? New word (ASCII letters, optional internal - or '): vela

  ✓ Added "vela" (#1): water — 水
  No existing words have a similar spelling.
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

### Natural-language meanings

- The built-in catalog contains 57 common concepts in six categories.
- Search the catalog by English, Chinese, or category name.
- Choose **Custom English — 中文 pair** to enter any other meaning.

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
the meaning.

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
| *(no command)* | Open the interactive menu. |

`TARGET` may be an entry ID, exact constructed word (case-insensitive), exact
English or Chinese gloss, or a unique partial match. Ambiguous targets list the
candidate IDs.

### Quick, non-interactive create

Supplying `--word`, `--english`, and `--chinese` together skips the prompts:

```console
$ python -m conlang_dict create --word vela --english water --chinese 水 --notes "river word"
```

Other examples:

```console
$ python -m conlang_dict list
$ python -m conlang_dict show vela
$ python -m conlang_dict search 水
$ python -m conlang_dict update vela --english sea --chinese 海
$ python -m conlang_dict update vela --clear-notes
$ python -m conlang_dict delete vela --yes
```

For guided updates, press Enter to keep the current value. Notes can be cleared
by entering `-` at the notes prompt, or non-interactively with `--clear-notes`.

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
   7  Quit
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
│   ├── concepts.py       # built-in English–Chinese meanings
│   ├── dictionary.py     # model, validation, JSON persistence
│   ├── display.py        # terminal styling and tables
│   └── similarity.py     # edit distance and spelling hints
├── tests/
│   ├── test_cli.py
│   ├── test_dictionary.py
│   └── test_similarity.py
├── pyproject.toml
└── README.md
```

## Tests

```console
$ python -m unittest discover -s tests -v
```

The suite covers validation, duplicate handling, CRUD persistence, file-format
errors, edit distance, similarity ranking, guided creation, and the CLI
commands.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success, or a cancelled action. |
| `1` | Validation, duplicate, missing entry, or dictionary-file error. |
| `2` | Invalid command-line usage. |
| `130` | Interrupted with Ctrl+C. |

## Notes and limitations

- The app is a single-user local tool; simultaneous writers are not coordinated.
- Similarity hints are advisory. Only exact case-insensitive spelling matches
  are rejected.
- `NO_COLOR=1` or `--no-color` disables ANSI styling. Colour is also disabled
  automatically when output is redirected.
