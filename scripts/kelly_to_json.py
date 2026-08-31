"""Convert the Swedish Kelly List spreadsheet into one JSON entry per word.

The script supplies only baseline dictionary definitions and inflections. Use
``enrich_json.py`` later if definitions, examples, or translations are missing.
It does not call an LLM and refuses to overwrite an existing JSON file unless
``--overwrite`` is provided.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from functions.inflection import extract_inflections


POS_MAP = {
    "adjective": "adjective", "adverb": "adverb", "aux verb": "verb",
    "conj": "conjunction", "det": "determiner", "interj": "interjection",
    "noun": "noun", "noun-en": "noun", "noun-ett": "noun",
    "numeral": "adjective", "particle": "particle", "prep": "preposition",
    "pronoun": "pronoun", "proper name": "proper noun", "subj": "conjunction",
    "verb": "verb", "particip": "adjective", "noun-en/-ett": "noun",
}


def clean_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame.columns = frame.columns.str.replace("-\n", "", regex=False).str.replace("\n", " ", regex=False).str.strip()
    frame = frame.fillna("")
    frame["Swedish items for translation"] = frame["Swedish items for translation"].str.replace(r"\s*\([^)]*\)", "", regex=True).str.strip()
    return frame


def filename(article: str, headword: str, pos: str) -> str:
    safe = re.sub(r'[<>:"/\\\\|?*]+', "_", headword.strip())
    return f"{article}_{safe}_{pos}.json" if article in {"en", "ett"} else f"{safe}_{pos}.json"


def fetch_entry(headword: str, retries: int) -> dict[str, Any]:
    url = f"https://freedictionaryapi.com/api/v1/entries/sv/{headword}"
    for attempt in range(retries + 1):
        response = requests.get(url, params={"translations": "true"}, timeout=30)
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()
        if attempt == retries:
            response.raise_for_status()
        wait = int(response.headers.get("Retry-After", "60"))
        print(f"Rate limited while looking up {headword!r}; waiting {wait} seconds.")
        time.sleep(wait)
    raise AssertionError("unreachable")


def matching_entries(data: dict[str, Any], pos: str, article: str) -> list[dict[str, Any]]:
    candidates = [entry for entry in data.get("entries", []) if entry.get("partOfSpeech") == pos]
    if pos == "noun":
        gender = "common gender" if article == "en" else "neuter"
        candidates = [entry for entry in candidates if any(gender in sense.get("tags", []) for sense in entry.get("senses", []))]
    return candidates[:2]


def build_entry(headword: str, article: str, pos: str, rank: int, level: str, dictionary: dict[str, Any]) -> dict[str, Any]:
    matches = matching_entries(dictionary, pos, article)
    definitions: list[dict[str, str]] = []
    forms: dict[str, Any] = {}
    for match in matches:
        forms = extract_inflections(match, pos)
        for sense in match.get("senses", []):
            examples = sense.get("examples") or []
            definitions.append({"definition": str(sense.get("definition") or ""), "example": str(examples[0]) if examples else "", "example_translation": ""})
            if len(definitions) == 2:
                break
        if len(definitions) == 2:
            break
    return {"frequency_rank": rank, "article": article, "word": headword, "definitions": definitions, "inflections": forms, "tags": [level, pos]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Kelly List .xls workbook.")
    parser.add_argument("--output", type=Path, required=True, help="Folder for entry JSON files.")
    parser.add_argument("--limit", type=int, help="Process only the first N entries.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing JSON files.")
    parser.add_argument("--retries", type=int, default=3, help="Retries after dictionary rate limits.")
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"Workbook not found: {args.input}")

    frame = clean_columns(pd.read_excel(args.input, sheet_name="Swedish_M3_CEFR"))
    if args.limit:
        frame = frame.head(args.limit)
    args.output.mkdir(parents=True, exist_ok=True)
    skipped = missing = 0
    seen: set[tuple[str, str, str]] = set()
    for number, (_, row) in enumerate(frame.iterrows(), start=1):
        headword, article = str(row["Swedish items for translation"]).strip(), str(row["Grammar"]).strip().lower()
        source_pos = str(row["Word classes"]).strip().lower()
        if source_pos not in POS_MAP:
            raise ValueError(f"Unsupported Kelly word class {source_pos!r} for {headword!r}")
        pos = POS_MAP[source_pos]
        identity = (article, headword, pos)
        if not headword or identity in seen:
            skipped += 1
            continue
        seen.add(identity)
        destination = args.output / filename(article, headword, pos)
        if destination.exists() and not args.overwrite:
            skipped += 1
            continue
        print(f"[{number}/{len(frame)}] {headword}", flush=True)
        dictionary = fetch_entry(headword, args.retries)
        entry = build_entry(headword, article, pos, int(row["ID"]), str(row["CEFR levels"]), dictionary)
        if not entry["definitions"]:
            missing += 1
        destination.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Finished. Skipped {skipped}; {missing} entries have no dictionary definition and can be enriched later.")


if __name__ == "__main__":
    main()
