# Operational scripts

These scripts are small, command-line building blocks from the production
pipeline. They intentionally operate on local data folders which are *not*
included in this repository. The files in `garbage/` from the original working
folder were one-off profile migrations and are intentionally not published.

The expected JSON shape is documented in [`../docs/architecture.md`](../docs/architecture.md).
Every script defaults to a dry or read-only action unless its command explicitly
creates output.

## Typical workflow

```powershell
# 1. Normalize a Kelly List workbook. This is the historical source-import
# script; it expects kelly_list.xls and writes to cache/json.
python scripts/apitojson.py

# 2. Convert a reviewed workbook of idioms and particle verbs to JSON.
python scripts/expressions_to_json.py --input path\\to\\expressions.xlsx --output data\\expressions

# 3. Propose LLM enrichment without changing the JSON source files.
python scripts/enrich_json.py propose --help

# 4. Inspect Azure TTS work before using any service credits.
python scripts/azure_tts_examples.py --source data\\json --output build\\audio --dry-run

# 5. Generate audio after setting the two environment variables shown in .env.example.
python scripts/azure_tts_examples.py --source data\\json --output build\\audio --synthesize

# 6. Regenerate the two explicitly flagged clips (optional repair utility).
python scripts/redo_flagged_audio.py

# 7. Verify that the JSON rank sequence is complete and unambiguous.
python scripts/verify_frequency_order.py --source data\\json
```

`azure_tts_examples.py` produces one MP3 for the first example sentence in each
JSON entry. It has retry handling and a conservative F0-friendly default pace of
19 requests per minute.

`redo_flagged_audio.py` contains two documented, Swedish-text overrides for
audio corrections and can optionally replace the matching media files through a
locally running AnkiConnect instance.

## Notes on the private production tooling

The complete production workflow also contained project-specific OpenAI Batch
proposal collection and AnkiConnect migration utilities. Those tools reference a
local Anki profile and source data, so they are deliberately not published as
drop-in commands: publishing a misleading one-click migration script would be
worse than documenting the method accurately. The public scripts above are
self-contained and reusable.
