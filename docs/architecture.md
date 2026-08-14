# Architecture

## Design principles

1. **Frequency is data, not an insertion accident.** Each note has a stable
   rank derived from the Kelly source, and expressions are placed after it.
2. **Fields remain separate.** Anki templates should compose fields, not parse
   a single formatted blob.
3. **Scheduling belongs to the learner.** Content updates must not overwrite a
   user’s review history.
4. **Every paid or generative step is optional and auditable.** Source JSON is
   reviewed before it reaches Anki.

## Content model

The current note schema separates:

- `Word`, `Sentence`, and `Audio`
- `Translated Word` and `Translated Sentence`
- `Meaning 2`, `Example 2`, and `Translated Sentence 2`
- `Inflections`
- `Frequency Order`

This supports Swedish-to-English and English-to-Swedish card types without
duplicating lexical content.

## Operational phases

### 1. Source normalization

The Kelly spreadsheet is normalized into one JSON document per lexical entry.
The original workbook has five duplicate word/article/POS rows; only one JSON
entry is retained for each duplicate identity.

### 2. Lexical enrichment

Dictionary data supplies baseline senses and inflections. A batched OpenAI
workflow fills only missing definitions, examples, and translations. Existing
definitions are preserved.

### 3. Speech synthesis

Only the first Swedish example of each note is synthesized. Azure Speech is
called at a deliberately conservative rate so the free tier can be used safely.

### 4. Anki integration

Existing notes are matched conservatively. Safe matches are updated in place to
preserve scheduling; ambiguous matches are retained for review rather than
silently overwritten. New cards are positioned in Kelly order.

## Verification

The build process audits the three important mappings:

1. Kelly Excel -> normalized JSON identity;
2. JSON -> active Anki note count and frequency rank;
3. Anki new-card `Due` positions -> `Frequency Order`.

The project’s final audit verified 8,551 active notes and an ascending new-card
queue for all remaining new cards.
