#!/usr/bin/env python3
"""
Anki field splitter — ONLY updates field content, no note type changes.
Run AFTER you have manually changed note types in Anki browser.

Usage:
  python anki_split_fields.py            # run on all notes
  python anki_split_fields.py --dry-run  # preview first 3 notes per deck, no changes
"""

import json
import re
import sys
import urllib.request

ANKI_CONNECT_URL = "http://localhost:8765"

SUBDECKS = [
    {"deck": "Svenska::Svenska adjektiv",                            "note_type": "Bàsica v2"},
    {"deck": "Svenska::Svenska adverb",                              "note_type": "Bàsica v2"},
    {"deck": "Svenska::Svenska Pronomen, interjektioner och siffror","note_type": "Bàsica v2"},
    {"deck": "Svenska::Svenska namn",                                "note_type": "Bàsica - Swedish Names v2"},
    {"deck": "Svenska::Svenska verb",                                "note_type": "Bàsica - Swedish Verbs v2"},
]

# Extra field name per note type
EXTRA_FIELD = {
    "Bàsica v2":                  None,
    "Bàsica - Swedish Names v2":  "Plural",
    "Bàsica - Swedish Verbs v2":  "Conjugation",
}

# ── AnkiConnect helper ────────────────────────────────────────────────────────

def anki(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    req = urllib.request.Request(ANKI_CONNECT_URL, payload)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        print(f"✗ Cannot reach AnkiConnect: {e}")
        print("  → Make sure Anki is open with AnkiConnect installed.")
        sys.exit(1)
    if result.get("error"):
        raise RuntimeError(f"AnkiConnect: {result['error']}")
    return result["result"]

# ── Field splitting ───────────────────────────────────────────────────────────

def split_word_field(text):
    """
    'ord (mening) [sound:x.mp3]'  →  (word, sentence, audio)
    Handles cases with no sentence, no audio, or both missing.
    """
    text = text.strip()

    # Extract [sound:...]
    audio_match = re.search(r'(\[sound:[^\]]+\])', text)
    audio = audio_match.group(1) if audio_match else ""
    if audio:
        text = text.replace(audio, "").strip()

    # Extract (sentence) — last parenthesised group
    match = re.match(r'^(.*?)\s*\((.+)\)\s*$', text, re.DOTALL)
    if match:
        word     = match.group(1).strip()
        sentence = match.group(2).strip()
    else:
        word     = text.strip()
        sentence = ""

    return word, sentence, audio

def split_translation_field(text):
    """
    'traducció (traducció frase)'  →  (translation, sentence_translation)
    """
    text = text.strip()
    match = re.match(r'^(.*?)\s*\((.+)\)\s*$', text, re.DOTALL)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return text.strip(), ""

# ── Core logic ────────────────────────────────────────────────────────────────

def process_note(note, dry_run=False):
    """Returns (new_fields_dict, changed: bool)"""
    fields = note["fields"]

    word_raw        = fields.get("Word", {}).get("value", "")
    translation_raw = fields.get("Translation", {}).get("value", "")

    word, sentence, audio               = split_word_field(word_raw)
    translation, sentence_translation   = split_translation_field(translation_raw)

    # Only update if there's actually something to split
    changed = bool(sentence or audio or sentence_translation)

    new_fields = {
        "Word":                 word,
        "Sentence":             sentence,
        "Audio":                audio,
        "Translation":          translation,
        "Sentence_Translation": sentence_translation,
    }

    return new_fields, changed

def run(dry_run=False):
    mode = "DRY RUN (no changes)" if dry_run else "LIVE"
    print(f"\n=== Anki Field Splitter — {mode} ===\n")

    total_ok = total_skip = total_error = 0

    for subdeck_info in SUBDECKS:
        deck      = subdeck_info["deck"]
        note_type = subdeck_info["note_type"]

        print(f"── {deck} ({note_type}) ──")

        note_ids = anki("findNotes", query=f'deck:"{deck}" note:"{note_type}"')
        print(f"   Found {len(note_ids)} notes")

        if not note_ids:
            print(f"   ⚠  No notes found — did you change the note type yet?")
            continue

        # In dry-run, only preview first 3
        sample = note_ids[:3] if dry_run else note_ids
        notes_info = anki("notesInfo", notes=sample)

        ok = skip = error = 0

        for note in notes_info:
            note_id = note["noteId"]
            try:
                new_fields, changed = process_note(note, dry_run)

                if dry_run:
                    fields = note["fields"]
                    print(f"\n   Note {note_id}:")
                    print(f"     Word (raw)        : {fields.get('Word',{}).get('value','')!r}")
                    print(f"     → Word            : {new_fields['Word']!r}")
                    print(f"     → Sentence        : {new_fields['Sentence']!r}")
                    print(f"     → Audio           : {new_fields['Audio']!r}")
                    print(f"     Translation (raw) : {fields.get('Translation',{}).get('value','')!r}")
                    print(f"     → Translation     : {new_fields['Translation']!r}")
                    print(f"     → Sent_Translation: {new_fields['Sentence_Translation']!r}")
                    continue

                if not changed:
                    skip += 1
                    continue

                anki("updateNoteFields", note={"id": note_id, "fields": new_fields})
                ok += 1

            except RuntimeError as e:
                print(f"   ✗ Note {note_id}: {e}")
                error += 1

        if not dry_run:
            print(f"   ✓ {ok} updated, {skip} skipped (nothing to split), {error} errors")
            total_ok    += ok
            total_skip  += skip
            total_error += error

    if not dry_run:
        print(f"\n=== Done ===")
        print(f"  Updated : {total_ok}")
        print(f"  Skipped : {total_skip}")
        print(f"  Errors  : {total_error}")
        if total_error == 0:
            print(f"  ✅ All done!")
        else:
            print(f"  ⚠  Check errors above.")

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run(dry_run=dry_run)
