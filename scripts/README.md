# Operational scripts

These scripts are small, command-line building blocks from the production
pipeline. They intentionally operate on local data folders which are *not*
included in this repository.

The expected JSON shape is documented in [`../docs/architecture.md`](../docs/architecture.md).
Every script defaults to a dry or read-only action unless its command explicitly
creates output.

## Typical workflow

```powershell
# 1. Convert a reviewed workbook of idioms and particle verbs to JSON.
python scripts/expressions_to_json.py --input path\\to\\expressions.xlsx --output data\\expressions

# 2. Inspect Azure TTS work before using any service credits.
python scripts/azure_tts_examples.py --source data\\json --output build\\audio --dry-run

# 3. Generate audio after setting the two environment variables shown in .env.example.
python scripts/azure_tts_examples.py --source data\\json --output build\\audio --synthesize

# 4. Verify that the JSON rank sequence is complete and unambiguous.
python scripts/verify_frequency_order.py --source data\\json
```

`azure_tts_examples.py` produces one MP3 for the first example sentence in each
JSON entry. It has retry handling and a conservative F0-friendly default pace of
19 requests per minute.

## Notes on the private production tooling

The complete production workflow also contained project-specific OpenAI Batch
proposal collection and AnkiConnect migration utilities. Those tools reference a
local Anki profile and source data, so they are deliberately not published as
drop-in commands: publishing a misleading one-click migration script would be
worse than documenting the method accurately. The public scripts above are
self-contained and reusable.
