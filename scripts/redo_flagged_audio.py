"""Regenerate the two Swedish example-audio files that were flagged for review.

This intentionally touches only ``en ätt`` (rank 437) and ``still`` (rank
3904). It never edits JSON. The two spoken strings below are explicit fixes:
the original ätt example included an English quotation, and the still JSON had
its Swedish and English example fields swapped.

Inspect first (no API call):
    python redo_flagged_audio.py

Create/replace the two cache MP3 files:
    python redo_flagged_audio.py --synthesize

Also replace the files in a currently open Anki profile through AnkiConnect:
    python redo_flagged_audio.py --synthesize --install-in-anki

After they have been generated once, install the cached files into a different
Anki profile without calling Azure again:
    python redo_flagged_audio.py --install-in-anki
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
import xml.sax.saxutils
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "cache" / "audio"
VOICE = "sv-SE-SofieNeural"
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"

# Keep these as explicit text overrides rather than changing the original data.
TARGETS = (
    {
        "rank": 437,
        "word": "en ätt",
        "stem": "en_ätt_noun",
        "text": "Var honom trofast och hans ätt. Gör kronan på hans hjässa lätt. Och all din tro till honom sätt.",
    },
    {
        "rank": 3904,
        "word": "still",
        "stem": "still_adjective",
        "text": "Vattnet var stilla på morgonen.",
    },
)


def synthesize(text: str, key: str, region: str) -> bytes:
    """Call Azure Speech once, retrying only temporary errors."""
    ssml = (
        '<speak version="1.0" xml:lang="sv-SE"><voice name="'
        + VOICE
        + '">'
        + xml.sax.saxutils.escape(text)
        + "</voice></speak>"
    ).encode("utf-8")
    request = Request(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml,
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
            "User-Agent": "swedish-anki-deck-audio-repair/1.0",
        },
        method="POST",
    )
    for attempt in range(4):
        try:
            with urlopen(request, timeout=30) as response:
                audio = response.read()
            if not audio:
                raise RuntimeError("Azure returned an empty audio response")
            return audio
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 3:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
                raise RuntimeError(f"Azure HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            if attempt == 3:
                raise RuntimeError(f"Azure network error: {exc.reason}") from exc
        time.sleep(2**attempt)
    raise AssertionError("unreachable")


def anki(action: str, **params: object) -> object:
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    request = Request("http://127.0.0.1:8765", data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=15) as response:
        reply = json.loads(response.read())
    if reply.get("error"):
        raise RuntimeError(f"AnkiConnect: {reply['error']}")
    return reply["result"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthesize", action="store_true", help="Call Azure and overwrite only the two cache MP3s.")
    parser.add_argument("--install-in-anki", action="store_true", help="Replace their existing Anki media files too; requires Anki + AnkiConnect.")
    args = parser.parse_args()
    for target in TARGETS:
        print(f"#{target['rank']}: {target['word']}\n  {target['text']}")
    if not args.synthesize and not args.install_in_anki:
        print("Dry run only. No files or API calls were made.")
        return

    key, region = os.environ.get("AZURE_SPEECH_KEY"), os.environ.get("AZURE_SPEECH_REGION")
    if args.synthesize and (not key or not region):
        parser.error("Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in this PowerShell session first.")
    if args.synthesize:
        OUTPUT.mkdir(parents=True, exist_ok=True)
    for target in TARGETS:
        destination = OUTPUT / f"{target['stem']}.mp3"
        if args.synthesize:
            print(f"Synthesizing #{target['rank']} ({target['word']})…", flush=True)
            audio = synthesize(str(target["text"]), key, region)
            temporary = destination.with_suffix(".mp3.part")
            temporary.write_bytes(audio)
            temporary.replace(destination)
            print(f"  wrote {destination}")
        else:
            if not destination.is_file() or destination.stat().st_size == 0:
                parser.error(f"Cached MP3 is missing: {destination}. Re-run with --synthesize.")
            audio = destination.read_bytes()
        if args.install_in_anki:
            media_name = f"sv_core__{target['stem']}.mp3"
            anki(
                "storeMediaFile",
                filename=media_name,
                data=base64.b64encode(audio).decode("ascii"),
                deleteExisting=True,
            )
            print(f"  replaced Anki media: {media_name}")


if __name__ == "__main__":
    main()
