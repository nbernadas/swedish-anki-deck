# Swedish Vocabulary A1–C2 for Anki

An open, reproducible pipeline for building a Swedish vocabulary deck from the
Kelly List. The current edition combines frequency-ranked vocabulary, separate
Anki fields, Swedish example audio, inflection data, particle verbs, and
idiomatic expressions.

> **Project status:** the published deck is a new unified edition, not a
> drop-in update for the earlier three-part releases. See
> [Migration notes](#migration-from-the-three-part-edition).

## What the published deck contains

| Component | Count |
| --- | ---: |
| Kelly List vocabulary notes | 8,420 |
| Particle verbs | 87 |
| Idiomatic expressions | 44 |
| Total notes | 8,551 |
| Swedish example-audio clips | 8,550 |

Each note stores the word, two possible senses, Swedish examples, English
translations, audio, available inflections, and a stable `Frequency Order`.
The rank is shown on-card as `#rank / 8551`.

## Why this project exists

Public Swedish decks often trade completeness for structure: frequency order,
audio, example quality, grammatical information, and card customization are
usually handled separately. This project treats deck construction as a data
pipeline instead of a one-off export.

The goal is a deck that is useful to learners and also inspectable: every
automated enrichment step can be audited, rerun, or replaced.

## Pipeline

```text
Kelly List (.xls)
   -> normalized entry JSON
   -> dictionary enrichment and inflections
   -> LLM completion of missing definitions/examples/translations
   -> Azure Swedish text-to-speech
   -> reviewed Anki notes and media
```

The implementation is documented in [docs/architecture.md](docs/architecture.md).

## Data sources and services

- **Kelly List**, Språkbanken, University of Gothenburg: frequency order,
  CEFR level, headword, and grammatical metadata.
- **Free Dictionary API**: baseline lexical data and available inflections.
- **OpenAI GPT-5.4 mini**: missing definitions, example sentences, and English
  translations. The enrichment run generated 1,545 definitions across 1,119
  entries where source data lacked a definition.
- **Microsoft Azure Speech** (`sv-SE-SofieNeural`): 8,550 Swedish audio clips.

Generated content is deliberately kept out of this repository. See
[docs/data-policy.md](docs/data-policy.md) for the rationale.

## Repository layout

```text
.
├── anki_split_fields.py    # Earlier compatibility utility (kept for history)
├── anki_wiktionary.py      # Earlier dictionary-enrichment experiment
├── docs/
│   ├── architecture.md     # Current pipeline and design decisions
│   └── data-policy.md      # Data, media, credentials, and licensing boundaries
├── scripts/
│   ├── azure_tts_examples.py       # Azure MP3 generation for first examples
│   ├── expressions_to_json.py      # Reviewed expression workbook -> JSON
│   └── verify_frequency_order.py   # Read-only rank integrity audit
├── sample.png              # Screenshot from the earlier public edition
└── README.md
```

The original scripts are retained to document the project’s evolution. The
reusable operational scripts are under `scripts/`; the raw JSON cache,
generated audio, user collection, API credentials, and packaged decks remain
deliberately private.

## Reproducibility and safety

The operational scripts use environment variables for paid services; never
commit keys. Typical local variables are:

```text
OPENAI_API_KEY=
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
```

Large/generated artifacts such as `cache/`, `audio/`, `.apkg` files, Anki
collections, and review reports are excluded from version control. This keeps
the repository lightweight and prevents accidental publication of personal
study data or service credentials.

## Migration from the three-part edition

The previous releases were published as separate Part 1–3 decks. This edition
uses a unified hierarchy and redesigned note types with separate fields for
examples, translations, audio, inflections, and rank.

Because Anki cannot reliably update previously imported notes after a note type
changes, users should import this edition as a new deck rather than merge it
into an older Part 1–3 installation. Users who already know a portion of the
vocabulary can suspend those cards or use Anki’s **Set Due Date** command to
place them directly in the review queue.

## Limitations

- Dictionary and LLM-generated material can contain mistakes. Learner feedback
  and corrections are welcome.
- The Kelly source contains five duplicate rows with identical word/article/POS
  identity; the deck stores one note for each unique entry.
- Audio is generated speech, not human studio recording.

## License

The code in this repository is released under the MIT License. Source datasets,
generated deck content, and external services remain subject to their own terms.
