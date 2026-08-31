"""Create or update a Swedish vocabulary deck in the open Anki profile.

This is a portable AnkiConnect exporter. It creates one model named
``Swedish Vocabulary (generated)`` and updates notes with the same ``Word``
and ``Frequency Order`` instead of replacing them, so existing card history is
kept. It never changes Anki unless ``--apply`` is supplied.

Typical use:
    python scripts/json_to_anki.py --core data/json --expressions data/expressions \
        --audio-dir build/audio --deck "Swedish Vocabulary" --apply

Anki must be open and the AnkiConnect add-on must be installed for --apply.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


ANKI_CONNECT_URL = "http://127.0.0.1:8765"
MODEL_NAME = "Swedish Vocabulary (generated)"
FIELDS = [
    "Frequency Order", "Word", "Part of Speech", "Sentence", "Audio",
    "Meaning 1", "Translation 1", "Meaning 2", "Sentence 2",
    "Translation 2", "Inflections", "Source Type",
]
CARD_NAME = "Swedish → English"
CSS = """
.card { font-family: Arial, sans-serif; font-size: 20px; text-align: left; color: #1f2933; background: #fbfcfe; }
.shell { max-width: 720px; margin: 0 auto; padding: 18px 22px; }
.rank, .label { color: #667085; font-size: 12px; letter-spacing: .06em; text-transform: uppercase; }
.word { font-size: 32px; font-weight: 700; margin: 3px 0 14px; }
.pos { color: #667085; font-size: 15px; font-weight: 400; }
.block { border-top: 1px solid #e4e7ec; margin-top: 14px; padding-top: 12px; }
.sentence { font-size: 22px; line-height: 1.35; }
.meaning { font-size: 19px; font-weight: 600; margin-top: 4px; }
.translation { color: #475467; font-style: italic; margin-top: 4px; }
.inflections { color: #475467; font-size: 15px; line-height: 1.45; }
.audio { display: inline-block; margin-left: 8px; vertical-align: middle; }
"""
FRONT = """<div class=\"shell\"><div class=\"rank\">#{{Frequency Order}}</div>
<div class=\"word\">{{Word}} {{#Part of Speech}}<span class=\"pos\">{{Part of Speech}}</span>{{/Part of Speech}}</div>
{{#Sentence}}<div class=\"block\"><div class=\"label\">Example</div><div class=\"sentence\">{{Sentence}} <span class=\"audio\">{{Audio}}</span></div></div>{{/Sentence}}
{{#Inflections}}<div class=\"block\"><div class=\"label\">Inflections</div><div class=\"inflections\">{{Inflections}}</div></div>{{/Inflections}}
</div>"""
BACK = """{{FrontSide}}<div class=\"shell\">
<div class=\"block\"><div class=\"label\">Meaning</div><div class=\"meaning\">{{Meaning 1}}</div>{{#Translation 1}}<div class=\"translation\">{{Translation 1}}</div>{{/Translation 1}}</div>
{{#Meaning 2}}<div class=\"block\"><div class=\"label\">Meaning 2</div><div class=\"meaning\">{{Meaning 2}}</div>{{#Sentence 2}}<div class=\"sentence\">{{Sentence 2}}</div>{{/Sentence 2}}{{#Translation 2}}<div class=\"translation\">{{Translation 2}}</div>{{/Translation 2}}</div>{{/Meaning 2}}
</div>"""


def anki(action: str, **params: Any) -> Any:
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    request = Request(ANKI_CONNECT_URL, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=90) as response:
        reply = json.loads(response.read())
    if reply.get("error"):
        raise RuntimeError(f"AnkiConnect {action}: {reply['error']}")
    return reply["result"]


def text(value: object) -> str:
    return html.escape(str(value or "").strip())


def word(entry: dict[str, Any]) -> str:
    return " ".join(part for part in (str(entry.get("article") or "").strip(), str(entry.get("word") or "").strip()) if part)


def part_of_speech(entry: dict[str, Any]) -> str:
    known = {"noun", "proper noun", "verb", "adjective", "adverb", "pronoun", "determiner", "preposition", "conjunction", "interjection", "particle", "partikelverb", "idiom", "expression"}
    return next((str(tag) for tag in entry.get("tags", []) if str(tag) in known), "")


def inflections(entry: dict[str, Any]) -> str:
    labels = {"plural": "Plural", "present": "Present", "past": "Past", "supine": "Supine", "imperative": "Imperative", "participle": "Participle", "comparative": "Comparative", "superlative": "Superlative"}
    forms = entry.get("inflections") or {}
    return " · ".join(f"<b>{label}:</b> {text(forms.get(key))}" for key, label in labels.items() if forms.get(key))


def audio_index(folders: list[Path]) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for folder in folders:
        if not folder.is_dir():
            raise ValueError(f"Audio folder does not exist: {folder}")
        for path in folder.rglob("*.mp3"):
            index.setdefault(path.stem, path)
            for prefix in ("sv_core__", "sv_partikelverb__", "sv_idioms__"):
                if path.stem.startswith(prefix):
                    index.setdefault(path.stem.removeprefix(prefix), path)
    return index


def entries(core: Path, expressions: Path | None) -> list[tuple[Path, dict[str, Any], str, int]]:
    if not core.is_dir():
        raise ValueError(f"Core JSON folder does not exist: {core}")
    result: list[tuple[Path, dict[str, Any], str, int]] = []
    for path in sorted(core.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        rank = entry.get("frequency_rank")
        if not isinstance(rank, int) or rank < 1:
            raise ValueError(f"{path}: frequency_rank must be a positive integer")
        result.append((path, entry, "Kelly List", rank))
    max_rank = max((item[3] for item in result), default=0)
    if expressions:
        if not expressions.is_dir():
            raise ValueError(f"Expressions JSON folder does not exist: {expressions}")
        expression_paths = sorted(expressions.rglob("*.json"), key=lambda path: (json.loads(path.read_text(encoding="utf-8")).get("source_order", 0), path.name))
        for offset, path in enumerate(expression_paths, start=1):
            result.append((path, json.loads(path.read_text(encoding="utf-8")), "Expression", max_rank + offset))
    return sorted(result, key=lambda item: item[3])


def note_fields(entry: dict[str, Any], rank: int, source: str, audio: Path | None) -> dict[str, str]:
    definitions = entry.get("definitions") or []
    first = definitions[0] if definitions else {}
    second = definitions[1] if len(definitions) > 1 else {}
    return {
        "Frequency Order": str(rank), "Word": text(word(entry)), "Part of Speech": text(part_of_speech(entry)),
        "Sentence": text(first.get("example")), "Audio": f"[sound:{audio.name}]" if audio else "",
        "Meaning 1": text(first.get("definition")), "Translation 1": text(first.get("example_translation")),
        "Meaning 2": text(second.get("definition")), "Sentence 2": text(second.get("example")),
        "Translation 2": text(second.get("example_translation")), "Inflections": inflections(entry), "Source Type": source,
    }


def ensure_model() -> None:
    if MODEL_NAME in anki("modelNames"):
        actual = anki("modelFieldNames", modelName=MODEL_NAME)
        if actual != FIELDS:
            raise RuntimeError(f"Existing {MODEL_NAME!r} has different fields. Rename it or use a new Anki profile.")
        return
    anki("createModel", modelName=MODEL_NAME, inOrderFields=FIELDS, css=CSS, isCloze=False, cardTemplates=[{"Name": CARD_NAME, "Front": FRONT, "Back": BACK}])


def existing_note_id(fields: dict[str, str]) -> int | None:
    ids = anki("findNotes", query=f'note:"{MODEL_NAME}" "Frequency Order:{fields["Frequency Order"]}"')
    if not ids:
        return None
    candidates = anki("notesInfo", notes=ids)
    exact = [note["noteId"] for note in candidates if note["fields"]["Word"]["value"] == fields["Word"]]
    if len(exact) > 1:
        raise RuntimeError(f"More than one existing note matches #{fields['Frequency Order']} {fields['Word']}")
    return exact[0] if exact else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True, help="Folder of Kelly entry JSON files.")
    parser.add_argument("--expressions", type=Path, help="Optional folder containing idiom and particle-verb JSON files.")
    parser.add_argument("--audio-dir", type=Path, action="append", default=[], help="Optional folder of MP3 files; may be repeated.")
    parser.add_argument("--deck", default="Swedish Vocabulary", help="Parent deck to create or update.")
    parser.add_argument("--limit", type=int, help="Use only the first N entries; useful for a test deck.")
    parser.add_argument("--apply", action="store_true", help="Write notes and audio to Anki. Default: preview only.")
    args = parser.parse_args()

    records = entries(args.core, args.expressions)
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be at least 1")
        records = records[:args.limit]
    audio = audio_index(args.audio_dir)
    planned = [(path, note_fields(entry, rank, source, audio.get(path.stem))) for path, entry, source, rank in records]
    print(f"Prepared {len(planned)} notes; {sum(bool(fields['Audio']) for _, fields in planned)} have local audio.")
    if not args.apply:
        print("Preview only. Open Anki with AnkiConnect, then re-run with --apply.")
        return

    ensure_model()
    created = updated = uploaded = 0
    for index, (path, fields) in enumerate(planned, start=1):
        deck = f"{args.deck}::{'Expressions' if fields['Source Type'] == 'Expression' else 'Vocabulary'}"
        anki("createDeck", deck=deck)
        matching_audio = audio.get(path.stem)
        if matching_audio:
            anki("storeMediaFile", filename=matching_audio.name, data=base64.b64encode(matching_audio.read_bytes()).decode("ascii"))
            uploaded += 1
        note_id = existing_note_id(fields)
        if note_id:
            anki("updateNoteFields", note={"id": note_id, "fields": fields})
            updated += 1
        else:
            anki("addNote", note={"deckName": deck, "modelName": MODEL_NAME, "fields": fields, "tags": ["swedish-vocabulary", fields["Source Type"].lower().replace(" ", "-")]})
            created += 1
        if index % 100 == 0 or index == len(planned):
            print(f"[{index}/{len(planned)}] created {created}, updated {updated}", flush=True)
    print(f"Finished: {created} created, {updated} updated, {uploaded} audio files uploaded.")


if __name__ == "__main__":
    main()
