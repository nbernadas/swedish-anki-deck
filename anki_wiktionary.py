import requests
import re
import html
import time

def get_definition(language, word):
    url = f"https://freedictionaryapi.com/api/v1/entries/{language}/{word}"

    for attempt in range(3):
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json()
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")

            if retry_after:
                wait_time = int(retry_after)
            else:
                wait_time = 2 ** attempt  # exponential backoff: 1,2,4,8,...
            
            print(f"Rate limited. Waiting {wait_time}s...")
            time.sleep(wait_time)
            continue
            #return f"Error: {response.status_code}"

        response.raise_for_status()
    raise Exception("Max retries exceeded")
    
    
def extract_headword(text):
    text = html.unescape(text)
    text = text.split("(")[0].strip()
    text = re.sub(r"^(en|ett)\s+", "", text, flags=re.IGNORECASE)
    return text.strip()

current_language = "sv"

headwords = []

with open("svenska.txt", "r", encoding="utf-8") as infile, \
     open("svenska_update.txt", "w", encoding="utf-8") as outfile:
    
    outfile.write("#separator:tab\n")
    outfile.write("#html:true\n")
    outfile.write("#tags column:4\n")

    kota = 0
    
    for line in infile:
        if line.startswith("#") or not line.strip():
            continue

        front = line.split("\t")[0]
        word = extract_headword(front)

        info = get_definition(current_language, word)

        entry = next(
            (
                e for e in info["entries"]
                if e.get("partOfSpeech") == "noun"
            ),
            None
        )

        forms = entry["forms"] if entry else []

        #forms = info["entries"][0]["forms"]

        result = next(
            (
                f["word"]
                for f in forms
                if {"indefinite", "nominative", "plural"}.issubset(f.get("tags", []))
            ),
            "-"
        )

        cols = line.rstrip("\n").split("\t")

        # ensure enough columns
        while len(cols) <= 2:
            cols.append("")

        # word = extract_word(cols[SOURCE_COL])
        cols[2] = result

        outfile.write("\t".join(cols) + "\n")

        kota = kota + 1

        print(kota)

        # if kota == 50:
        #    break