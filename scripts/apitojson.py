import json
from pathlib import Path
import pandas as pd
import requests
import time

from functions.inflection import extract_inflections

JSON_DIR = Path("cache/json")
JSON_DIR.mkdir(parents=True, exist_ok=True)

# Opening the main source, the Kelly List.
df = pd.read_excel(
    "kelly_list.xls",
    sheet_name="Swedish_M3_CEFR"
)

# Format columns names.
df.columns = (
    df.columns
      .str.replace("-\n", "", regex=False)  # Gram-\nmar -> Grammar
      .str.replace("\n", " ", regex=False)
      .str.strip()
)
    
# Remove everything inside parentheses (including the parentheses)
df["Swedish items for translation"] = df["Swedish items for translation"].str.replace(
    r"\s*\([^)]*\)", "", regex=True
)

df = df.fillna("")

# Dictionary to map the word class terminology of Kelly and Dictionary API.
POS_MAP = {
    "adjective": "adjective",
    "adverb": "adverb",
    "aux verb": "verb",
    "conj": "conjunction",
    "det": "determiner",
    "interj": "interjection",
    "noun": "noun",
    "noun-en": "noun",
    "noun-ett": "noun",
    "numeral": "adjective",
    "particle": "particle",
    "prep": "preposition",
    "pronoun": "pronoun",
    "proper name": "proper noun",
    "subj": "conjunction",
    "verb": "verb",
    "particip": "adjective",
    "noun-en/-ett": "noun"
}

# Iteration over each word, over 8000.
debug = 10000
non_existent_words = 0
non_existent_sentence = 0
current_word = 1
for _, row in df.iterrows():
    print(current_word)
    current_word += 1

    if current_word == debug + 1:
        break

    # We get the word itself and its word class (pretty relevant, a word could be multiple things (adverb, adjective, etc.), specially in asian languages but also european).
    word = row["Swedish items for translation"]
    expected_pos = POS_MAP[row["Word classes"].strip().lower()]

    # We call the Dictionary API and get the JSON. Note Dictionary API returns a JSON even if word does not exist.
    while True:
        response = requests.get(
            f"https://freedictionaryapi.com/api/v1/entries/sv/{word}",
            params={"translations": "true"}
        )

        if response.status_code == 429:
            print("Rate limit reached. Waiting 1 hour...")
            time.sleep(3600)  # 1 hour
            continue  # retry the same request

        break  # request succeeded (or failed for another reason)

    data = response.json()

    if expected_pos == "noun":
        expected_gender = (
            "common gender" if row["Grammar"].strip().lower() == "en"
            else "neuter"
        )

        matching_entries = [
            entry
            for entry in data["entries"]
            if (
                entry["partOfSpeech"] == expected_pos
                and any(
                    expected_gender in sense.get("tags", [])
                    for sense in entry["senses"]
                )
            )
        ][:2]
    else:
        matching_entries = [
            entry
            for entry in data["entries"]
            if entry["partOfSpeech"] == expected_pos
        ][:2]

    # If word is not found in Dictionary (maybe misspelling or colloquial word), we invoke LLM API to generate an equivalent JSON.
    if not matching_entries:
        print(f"{word}: no matching {expected_pos}")
        non_existent_words += 1

    # Now we fetch what defintions and examples from the JSON. Translations are mostly geenrated with LLM, as well as the examples really.
    definitions = []
    inflections = {}

    for entry in matching_entries:
        inflections = extract_inflections(entry, expected_pos)

        for sense in entry["senses"]:

            definition = sense["definition"]

            if sense["examples"]:
                example = sense["examples"][0]
            else:
                example = ""
                non_existent_sentence += 1

            example_translation = ""

            definitions.append({
                "definition": definition,
                "example": example,
                "example_translation": example_translation,
            })

            if len(definitions) == 2:
                break

        if len(definitions) == 2:
            break

    entry_json = {
    "frequency_rank": row["ID"],
    "article": row["Grammar"],
    "word": word,
    "definitions": definitions,
    "inflections": inflections,
    "tags": [row["CEFR levels"], expected_pos]
    }

    article = row["Grammar"].strip().lower()

    if article in {"en", "ett"}:
        json_path = JSON_DIR / f"{article}_{word}_{expected_pos}.json"
    else:
        json_path = JSON_DIR / f"{word}_{expected_pos}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(entry_json, f, ensure_ascii=False, indent=4)

print(non_existent_words/debug)
print(non_existent_sentence/debug)
