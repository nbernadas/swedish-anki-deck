# Swedish Vocabulary A1–C2 for Anki

The source code behind a Swedish vocabulary deck ordered by frequency. The
published deck contains **8,551 notes**: 8,420 Kelly List entries, 87 particle
verbs, and 44 idiomatic expressions.

Each card can include an English meaning, up to two Swedish example sentences
with translations, available inflections, and audio for the first example.

## What is in this repository

- `scripts/` — the Python tools used to build and check the deck.
- `.env.example` — the names of the optional API settings.
- `requirements.txt` — Python dependencies.

The generated JSON files, MP3 audio, Anki collection, and `.apkg` export are
not committed. They are build outputs and may be published separately later.
Never commit API keys or an Anki collection containing personal review data.

## How the deck is made

```text
Kelly List → JSON → enrichment → audio → Anki
```

The scripts are independent building blocks rather than a one-click installer:

| Script | Purpose |
| --- | --- |
| `kelly_to_json.py` | Imports the Kelly List and obtains baseline dictionary data. |
| `enrich_json.py` | Proposes missing definitions, examples, and translations through the OpenAI Batch API. |
| `expressions_to_json.py` | Converts the reviewed idioms/particle-verbs spreadsheet to JSON. |
| `json_to_audio.py` | Generates Swedish MP3s for first example sentences. |
| `json_to_anki.py` | Creates or updates a self-contained Anki deck through AnkiConnect. |
| `redo_flagged_audio.py` | Recreates two individually corrected audio clips. |
| `verify_json_frequency.py` | Checks frequency ranks without changing data. |

Install the dependencies with:

```powershell
python -m pip install -r requirements.txt
```

For OpenAI or Azure steps, set the variables listed in `.env.example` in your
shell. The source files document their command-line options:

```powershell
python scripts/enrich_json.py --help
python scripts/json_to_audio.py --help
python scripts/json_to_anki.py --help
```

`json_to_anki.py` is intentionally a clean exporter, not a migration tool for
someone else's pre-existing collection. It creates a model named *Swedish
Vocabulary (generated)* and only updates notes that it previously made. This
means it can preserve a user's review history while avoiding unsafe guesses
about unrelated notes.

## Minimal build sequence

```powershell
# 1. Kelly List spreadsheet → JSON
python scripts/kelly_to_json.py --input kelly_list.xls --output data/json

# 2. Optional: review a spreadsheet of particle verbs and idioms → JSON
python scripts/expressions_to_json.py --input expressions.xlsx --output data/expressions --write

# 3. Optional: fill missing fields cheaply with OpenAI Batch, then review and apply
python scripts/enrich_json.py batch-submit --source data/json
python scripts/enrich_json.py batch-collect --batch-id YOUR_BATCH_ID --source data/json
python scripts/enrich_json.py apply --source data/json --apply

# 4. Optional: first Swedish example → MP3
python scripts/json_to_audio.py --source data/json --output build/audio --synthesize
# Repeat with data/expressions/partikelverb or data/expressions/idioms if needed.

# 5. JSON (+ optional MP3) → Anki. AnkiConnect must be enabled.
python scripts/json_to_anki.py --core data/json --expressions data/expressions --audio-dir build/audio --apply
```

## Sources and generated content

- **Kelly List** (Språkbanken, University of Gothenburg): frequency rank, CEFR
  level, headword, and grammatical metadata.
- **Free Dictionary API / Wiktionary**: baseline lexical data and inflections.
- **OpenAI GPT-5.4 mini**: only fills missing definitions, examples, and
  English translations; existing definitions are retained.
- **Azure Speech, `sv-SE-SofieNeural`**: Swedish example-sentence audio.

Generated material can contain errors. Corrections are welcome: open an issue
with the Swedish headword, the proposed correction, and a source if possible.

## License

The code is released under the [MIT License](LICENSE). Source data and
generated deck content remain subject to the terms of their respective sources
and services.
