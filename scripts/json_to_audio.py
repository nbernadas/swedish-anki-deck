"""Create Azure Speech MP3 files for the first Swedish example in each JSON entry.

The program never edits JSON. First inspect the planned work with ``--dry-run``.
To synthesize, set ``AZURE_SPEECH_KEY`` and ``AZURE_SPEECH_REGION`` in the
current shell, then run with ``--synthesize``.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import xml.sax.saxutils
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


VOICE = "sv-SE-SofieNeural"
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
F0_REQUESTS_PER_MINUTE = 19  # Conservative Azure F0 pace (20 standard requests/minute).


def collect_jobs(source: Path, output: Path) -> list[dict[str, object]]:
    """Read first-definition examples in parallel; Windows may be slow per file."""
    def read_one(path: Path) -> dict[str, object] | None:
        entry = json.loads(path.read_text(encoding="utf-8"))
        definitions = entry.get("definitions") or []
        example = definitions[0].get("example", "").strip() if definitions else ""
        if not example or not any(character.isalnum() for character in example):
            return None
        return {
            "source": path.name,
            "example": example,
            "characters": len(example),
            "path": output / f"{path.stem}.mp3",
        }

    with ThreadPoolExecutor(max_workers=16) as pool:
        return [job for job in pool.map(read_one, sorted(source.glob("*.json"))) if job]


def request_audio(text: str, key: str, region: str, retries: int) -> bytes:
    escaped = xml.sax.saxutils.escape(text)
    ssml = f'<speak version="1.0" xml:lang="sv-SE"><voice name="{VOICE}">{escaped}</voice></speak>'
    request = Request(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
            "User-Agent": "swedish-anki-deck/1.0",
        },
        method="POST",
    )
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=30) as response:
                audio = response.read()
            if not audio:
                raise RuntimeError("Azure returned an empty audio response")
            return audio
        except HTTPError as exc:
            retryable = exc.code in {429, 500, 502, 503, 504}
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            if not retryable or attempt == retries:
                raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            if attempt == retries:
                raise RuntimeError(f"Network error: {exc.reason}") from exc
        time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Folder containing entry JSON files.")
    parser.add_argument("--output", type=Path, required=True, help="Folder for MP3 files and reports.")
    parser.add_argument("--dry-run", action="store_true", help="Count work without calling Azure or writing files.")
    parser.add_argument("--synthesize", action="store_true", help="Call Azure and create missing MP3 files.")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate MP3 files that already exist.")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--requests-per-minute", type=int, default=F0_REQUESTS_PER_MINUTE)
    args = parser.parse_args()
    if args.dry_run == args.synthesize:
        parser.error("Choose exactly one: --dry-run or --synthesize")
    if not args.source.is_dir() or args.requests_per_minute < 1:
        parser.error("--source must exist and --requests-per-minute must be at least 1")

    print("Reading JSON entries…", flush=True)
    jobs = collect_jobs(args.source, args.output)
    pending = [job for job in jobs if args.overwrite or not Path(job["path"]).is_file()]
    characters = sum(int(job["characters"]) for job in pending)
    print(f"Found {len(jobs)} first-definition examples.")
    print(f"Pending audio files: {len(pending)} ({characters:,} characters).")
    print(f"Voice: {VOICE}; output: {args.output}")
    if args.dry_run:
        print(f"Minimum time at {args.requests_per_minute}/minute: {len(pending) * 60 / args.requests_per_minute / 3600:.1f} hours.")
        return

    key, region = os.environ.get("AZURE_SPEECH_KEY"), os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        parser.error("Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in this shell first.")
    args.output.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, str]] = []
    interval, next_request = 60 / args.requests_per_minute, time.monotonic()
    for index, job in enumerate(pending, start=1):
        print(f"[{index}/{len(pending)}] {job['source']}", flush=True)
        try:
            wait = next_request - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            audio = request_audio(str(job["example"]), key, region, args.retries)
            destination = Path(job["path"])
            temporary = destination.with_suffix(".mp3.part")
            temporary.write_bytes(audio)
            temporary.replace(destination)
            next_request = max(next_request + interval, time.monotonic())
        except RuntimeError as exc:
            failures.append({"source": str(job["source"]), "error": str(exc)})
            print(f"  failed: {exc}", flush=True)
    if failures:
        report = args.output / "failures.jsonl"
        report.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in failures), encoding="utf-8")
        print(f"Finished with {len(failures)} failures; see {report}.")
    else:
        print(f"Finished: wrote {len(pending)} MP3 files to {args.output}.")


if __name__ == "__main__":
    main()
