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
Kelly List → entry JSON → dictionary/LLM enrichment → Azure audio → Anki
```

The scripts are independent building blocks rather than a one-click installer:

| Script | Purpose |
| --- | --- |
| `apitojson.py` | Imports the Kelly List and obtains baseline dictionary data. |
| `enrich_json.py` | Proposes missing definitions, examples, and translations through the OpenAI Batch API. |
| `expressions_to_json.py` | Converts the reviewed idioms/particle-verbs spreadsheet to JSON. |
| `azure_tts_examples.py` | Generates Swedish MP3s for first example sentences. |
| `redo_flagged_audio.py` | Recreates two individually corrected audio clips. |
| `verify_frequency_order.py` | Checks frequency ranks without changing data. |

Install the dependencies with:

```powershell
python -m pip install -r requirements.txt
```

For OpenAI or Azure steps, copy `.env.example` to a local `.env` file and add
your own credentials. The source files document their command-line options:

```powershell
python scripts/enrich_json.py --help
python scripts/azure_tts_examples.py --help
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
