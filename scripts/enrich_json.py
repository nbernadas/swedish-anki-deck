"""Propose and, only after review, apply LLM enrichments to Anki entry JSONs.

The default command never changes files under cache/json.  It calls the API and
writes reviewable proposals to a JSONL file.  A separate explicit `apply`
command applies a reviewed proposal file.

Requires only Python's standard library and OPENAI_API_KEY.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "cache" / "json"
DEFAULT_PROPOSALS = ROOT / "review" / "enrichment_proposals.jsonl"
DEFAULT_FAILURES = ROOT / "review" / "enrichment_failures.jsonl"
API_URL = "https://api.openai.com/v1/responses"
API_BASE_URL = "https://api.openai.com/v1"

INFLECTIONS_BY_POS = {
    "noun": ("plural",),
    "verb": ("present", "past", "supine", "imperative", "participle"),
    "adjective": ("plural", "comparative", "superlative"),
}

SYSTEM_PROMPT = """You are a careful Swedish lexicographer preparing concise Anki data.
The entry's definitions and inflections are source data: never replace, delete, or
reword an existing value. Return only values requested in the provided task.

Definitions and translations must be English. Examples must be natural, idiomatic,
modern standard Swedish, short enough for a learner, and must demonstrate the
specified sense. Translate each example faithfully into natural English.

When definitions are absent, create one definition and a second only when it is a
clearly distinct, common, modern sense. Do not add archaic, historical, technical,
regional, or extremely rare senses merely to reach two. Supply an example and an
English translation for every new definition.

For inflections use only modern standard forms. For nouns, `plural` means the
indefinite nominative plural. For verbs use active indicative present and past,
supine, imperative, and present participle. For adjectives use positive indefinite
plural, comparative, and superlative. If a requested form genuinely does not exist,
return null for it.

Response contract: if definitions_are_missing is true, put the new entries in
new_definitions and leave definition_updates empty. Otherwise leave
new_definitions empty and return exactly one definition_updates item for every
input definitions item. The need_example and need_example_translation booleans
are authoritative: true means the input value is empty and you MUST return a
non-empty string for that field; false means it already has a value and you
MUST return null for that field. Do not infer this from whether the JSON key
exists. In inflections, return a string only for a requested missing form and
null for every other form.
"""

PATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "new_definitions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "definition": {"type": "string"},
                    "example": {"type": "string"},
                    "example_translation": {"type": "string"},
                },
                "required": ["definition", "example", "example_translation"],
            },
            "maxItems": 2,
        },
        "definition_updates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "index": {"type": "integer", "minimum": 0},
                    "example": {"type": ["string", "null"]},
                    "example_translation": {"type": ["string", "null"]},
                },
                "required": ["index", "example", "example_translation"],
            },
        },
        "inflections": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "plural": {"type": ["string", "null"]},
                "present": {"type": ["string", "null"]},
                "past": {"type": ["string", "null"]},
                "supine": {"type": ["string", "null"]},
                "imperative": {"type": ["string", "null"]},
                "participle": {"type": ["string", "null"]},
                "comparative": {"type": ["string", "null"]},
                "superlative": {"type": ["string", "null"]},
            },
            "required": [
                "plural", "present", "past", "supine", "imperative", "participle",
                "comparative", "superlative",
            ],
        },
    },
    "required": ["new_definitions", "definition_updates", "inflections"],
}

TRANSLATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "index": {"type": "integer", "minimum": 0},
                    "example": {"type": "string", "minLength": 1},
                    "example_translation": {"type": "string", "minLength": 1},
                },
                "required": ["index", "example", "example_translation"],
            },
        },
        "inflections": copy.deepcopy(PATCH_SCHEMA["properties"]["inflections"]),
    },
    "required": ["translations", "inflections"],
}

INFLECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "inflections": copy.deepcopy(PATCH_SCHEMA["properties"]["inflections"]),
    },
    "required": ["inflections"],
}


def pos_of(entry: dict[str, Any]) -> str:
    tags = entry.get("tags", [])
    for pos in INFLECTIONS_BY_POS:
        if pos in tags:
            return pos
    return ""


def needs_enrichment(entry: dict[str, Any]) -> bool:
    definitions = entry.get("definitions", [])
    if not definitions:
        return True
    if any(not item.get("example") or not item.get("example_translation") for item in definitions):
        return True
    pos = pos_of(entry)
    required = INFLECTIONS_BY_POS.get(pos, ())
    present = entry.get("inflections", {})
    return any(not present.get(key) for key in required)


def task_for(entry: dict[str, Any]) -> dict[str, Any]:
    """Send only data relevant to fields that are missing."""
    pos = pos_of(entry)
    definitions = entry.get("definitions", [])
    current_inflections = entry.get("inflections", {})
    missing_inflections = [
        key for key in INFLECTIONS_BY_POS.get(pos, ()) if not current_inflections.get(key)
    ]
    task: dict[str, Any] = {
        "word": entry.get("word", ""),
        "part_of_speech": pos or entry.get("tags", []),
        "article": entry.get("article", ""),
        "missing_inflections": missing_inflections,
        "definitions": [],
        "definitions_are_missing": not definitions,
    }
    if definitions:
        for index, item in enumerate(definitions):
            missing_example = not item.get("example")
            missing_translation = not item.get("example_translation")
            if missing_example or missing_translation:
                task["definitions"].append(
                    {
                        "index": index,
                        "definition": item.get("definition", ""),
                        "example": item.get("example", "") if missing_translation else "",
                        "need_example": missing_example,
                        "need_example_translation": missing_translation,
                    }
                )
    return task


def response_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    # Compatibility fallback if output_text is absent.
    parts: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    return "".join(parts)


def ask_model(
    task: dict[str, Any], model: str, api_key: str, timeout: int, correction: str = ""
) -> dict[str, Any]:
    payload = response_payload(task, model, correction)
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API returned HTTP {exc.code}: {details}") from exc
    try:
        return json.loads(response_text(json.loads(response_body)))
    except json.JSONDecodeError as exc:
        raise ValueError("The API did not return valid patch JSON") from exc


def is_translation_only(task: dict[str, Any]) -> bool:
    return bool(task["definitions"]) and all(
        item["need_example_translation"] for item in task["definitions"]
    )


def response_payload(task: dict[str, Any], model: str, correction: str = "", translation_only: bool = False) -> dict[str, Any]:
    if translation_only:
        compact_task = {
            "word": task["word"],
            "items": [{"index": item["index"], "definition": item["definition"], "existing_example": item["example"], "need_example": item["need_example"]} for item in task["definitions"]],
            "missing_inflections": task["missing_inflections"],
        }
        return {
            "model": model,
            "instructions": "For every item, return a short, natural Swedish example and its natural English translation. If existing_example is non-empty, preserve its meaning by translating that example; the returned example may repeat it. If existing_example is empty, create an example that demonstrates the definition. Return non-empty strings for both fields and do not omit or alter an index. Fill only the listed missing inflections with modern standard Swedish forms; return null for all other inflection fields.",
            "input": json.dumps(compact_task, ensure_ascii=False, separators=(",", ":")),
            "text": {"format": {"type": "json_schema", "name": "example_translations", "strict": True, "schema": TRANSLATION_SCHEMA}},
            "max_output_tokens": 300,
        }
    return {
        "model": model,
        "instructions": SYSTEM_PROMPT + correction,
        "input": json.dumps(task, ensure_ascii=False, separators=(",", ":")),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "anki_entry_patch",
                "strict": True,
                "schema": PATCH_SCHEMA,
            }
        },
        "max_output_tokens": 500,
    }


def translation_patch(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "new_definitions": [],
        "definition_updates": [
            {"index": item["index"], "example": item["example"], "example_translation": item["example_translation"]}
            for item in response["translations"]
        ],
        "inflections": response["inflections"],
    }


def inflection_payload(entry: dict[str, Any], model: str) -> dict[str, Any]:
    pos = pos_of(entry)
    missing = [key for key in INFLECTIONS_BY_POS.get(pos, ()) if not entry.get("inflections", {}).get(key)]
    return {
        "model": model,
        "instructions": "You provide modern standard Swedish inflections for Anki. Return a non-null form for every listed missing form that genuinely exists; use null only when the word is truly defective, invariable, or not gradable. Never invent an archaic or rare form. Noun plural means indefinite nominative plural. Adjective plural means positive indefinite plural; comparative and superlative must be supplied when the adjective is gradable. Verb forms are active indicative present and past, supine, imperative, and present participle.",
        "input": json.dumps({"word": entry.get("word", ""), "article": entry.get("article", ""), "part_of_speech": pos, "definitions": [x.get("definition", "") for x in entry.get("definitions", [])], "missing_inflections": missing}, ensure_ascii=False, separators=(",", ":")),
        "text": {"format": {"type": "json_schema", "name": "anki_inflections", "strict": True, "schema": INFLECTION_SCHEMA}},
        "max_output_tokens": 150,
    }


def inflection_patch(response: dict[str, Any]) -> dict[str, Any]:
    return {"new_definitions": [], "definition_updates": [], "inflections": response["inflections"]}


def validate_patch(entry: dict[str, Any], patch: dict[str, Any]) -> None:
    definitions = entry.get("definitions", [])
    if definitions and patch["new_definitions"]:
        raise ValueError("Patch attempted to replace existing definitions")
    if not definitions and len(patch["new_definitions"]) > 2:
        raise ValueError("Patch contains more than two new definitions")
    for item in patch["new_definitions"]:
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in item):
            raise ValueError("Every new definition needs definition, example, and translation")
    seen: set[int] = set()
    for update in patch["definition_updates"]:
        index = update["index"]
        if index in seen or not 0 <= index < len(definitions):
            raise ValueError("Invalid or duplicate definition update index")
        seen.add(index)
        original = definitions[index]
        if original.get("example") and update["example"] not in (None, ""):
            raise ValueError("Patch attempted to replace an existing example")
        if original.get("example_translation") and update["example_translation"] not in (None, ""):
            raise ValueError("Patch attempted to replace an existing example translation")
        if not original.get("example") and not update["example"]:
            raise ValueError("Missing proposed example")
        if not original.get("example_translation") and not update["example_translation"]:
            raise ValueError("Missing proposed example translation")
    expected_updates = {
        index
        for index, item in enumerate(definitions)
        if not item.get("example") or not item.get("example_translation")
    }
    if seen != expected_updates:
        raise ValueError("Patch did not update exactly the definitions with missing fields")
    allowed = set(INFLECTIONS_BY_POS.get(pos_of(entry), ()))
    for key, value in patch["inflections"].items():
        # The strict API schema contains every possible key; null means no proposal.
        if value is None:
            continue
        if key not in allowed:
            raise ValueError(f"Unexpected inflection key: {key}")
        if entry.get("inflections", {}).get(key):
            raise ValueError(f"Patch attempted to replace inflection: {key}")
        if not isinstance(value, str):
            raise ValueError(f"Invalid value for inflection: {key}")


def preserve_existing_values(entry: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Discard model attempts to repeat source values before validating its patch."""
    clean = copy.deepcopy(patch)
    if entry.get("definitions"):
        clean["new_definitions"] = []
    for update in clean.get("definition_updates", []):
        index = update.get("index")
        if not isinstance(index, int) or not 0 <= index < len(entry.get("definitions", [])):
            continue
        original = entry["definitions"][index]
        if original.get("example"):
            update["example"] = None
        if original.get("example_translation"):
            update["example_translation"] = None
    for key in list(clean.get("inflections", {})):
        if key not in INFLECTIONS_BY_POS.get(pos_of(entry), ()):
            clean["inflections"][key] = None
        elif entry.get("inflections", {}).get(key):
            clean["inflections"][key] = None
    return clean


def merge(entry: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Merge validated values only into empty fields; never delete source data."""
    updated = copy.deepcopy(entry)
    if not updated.get("definitions"):
        updated["definitions"] = patch["new_definitions"]
    for change in patch["definition_updates"]:
        definition = updated["definitions"][change["index"]]
        if not definition.get("example") and change["example"]:
            definition["example"] = change["example"]
        if not definition.get("example_translation") and change["example_translation"]:
            definition["example_translation"] = change["example_translation"]
    inflections = updated.setdefault("inflections", {})
    for key, value in patch["inflections"].items():
        if not inflections.get(key) and value:
            inflections[key] = value
    return updated


def iter_entries(source: Path):
    yield from sorted(source.glob("*.json"))


def propose(args: argparse.Namespace) -> int:
    paths = [path for path in iter_entries(args.source) if needs_enrichment(load_json(path))]
    if args.only:
        selected = set(args.only)
        paths = [path for path in paths if path.name in selected]
    already_proposed = proposed_sources(args.proposals)
    paths = [path for path in paths if path.name not in already_proposed]
    if args.limit is not None:
        paths = paths[: args.limit]
    if args.dry_run:
        print(f"Found {len(paths)} entries that need enrichment. No API request was made.")
        for path in paths:
            print(path.name)
        return 0
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set; no request was made.", file=sys.stderr)
        return 2
    print(f"Found {len(paths)} entries that need enrichment.", flush=True)
    args.proposals.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    mode = "a" if args.proposals.exists() else "w"
    with args.proposals.open(mode, encoding="utf-8") as output, args.failures.open("a", encoding="utf-8") as failures:
        for number, path in enumerate(paths, start=1):
            entry = load_json(path)
            patch: dict[str, Any] | None = None
            task = task_for(entry)
            try:
                try:
                    print(f"[{number}/{len(paths)}] requesting {path.name}...", flush=True)
                    patch = ask_model(task, args.model, api_key, args.timeout)
                    patch = preserve_existing_values(entry, patch)
                    validate_patch(entry, patch)
                except ValueError as first_error:
                    # A small model may occasionally return null for a required field.
                    # Retry once with the exact validation failure instead of silently
                    # losing the entry from the review file.
                    print(f"[{number}/{len(paths)}] retrying {path.name}: {first_error}", flush=True)
                    correction = (
                        "\nYour previous response failed validation: " + str(first_error)
                        + ". Return a corrected complete patch now. In particular, every "
                        "field marked need_example or need_example_translation true must be "
                        "a non-empty string, never null.\n"
                    )
                    patch = ask_model(task, args.model, api_key, args.timeout, correction)
                    patch = preserve_existing_values(entry, patch)
                    validate_patch(entry, patch)
                record = {"source": path.name, "task": task_for(entry), "patch": patch}
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
                print(f"[{number}/{len(paths)}] proposed {path.name}")
            except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError, KeyError) as exc:
                print(f"[{number}/{len(paths)}] skipped {path.name}: {exc}", file=sys.stderr)
                failure = {"source": path.name, "task": task, "patch": patch, "error": str(exc)}
                failures.write(json.dumps(failure, ensure_ascii=False) + "\n")
            if args.delay:
                time.sleep(args.delay)
    print(f"Added {written} proposals to {args.proposals}. Source JSONs were not changed.")
    return 0


def proposed_sources(proposals: Path) -> set[str]:
    """Return valid completed proposal names so reruns do not charge for them again."""
    if not proposals.exists():
        return set()
    names: set[str] = set()
    with proposals.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                source = json.loads(line).get("source")
            except json.JSONDecodeError:
                continue
            if isinstance(source, str):
                names.add(source)
    return names


def api_json(method: str, path: str, api_key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        API_BASE_URL + path,
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API returned HTTP {exc.code}: {details}") from exc


def upload_batch_file(path: Path, api_key: str) -> dict[str, Any]:
    boundary = "----ankiBatchBoundary7MA4YWxkTrZu0gW"
    content = path.read_bytes()
    body = b"".join([
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\nbatch\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: application/jsonl\r\n\r\n".encode(),
        content,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    request = urllib.request.Request(
        API_BASE_URL + "/files",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"File upload failed with HTTP {exc.code}: {details}") from exc


def pending_paths(source: Path, proposals: Path) -> list[Path]:
    known = proposed_sources(proposals)
    return [path for path in iter_entries(source) if needs_enrichment(load_json(path)) and path.name not in known]


def inflection_pending_paths(source: Path) -> list[Path]:
    paths = []
    for path in iter_entries(source):
        entry = load_json(path)
        if any(not entry.get("inflections", {}).get(key) for key in INFLECTIONS_BY_POS.get(pos_of(entry), ())):
            paths.append(path)
    return paths


def batch_submit(args: argparse.Namespace) -> int:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set; no batch was submitted.", file=sys.stderr)
        return 2
    paths = inflection_pending_paths(args.source) if args.inflections_only else pending_paths(args.source, args.proposals)
    if args.limit is not None:
        paths = paths[: args.limit]
    if not paths:
        print("No pending entries to submit.")
        return 0
    args.proposals.parent.mkdir(parents=True, exist_ok=True)
    request_file = args.proposals.parent / "batch_requests_pending.jsonl"
    with request_file.open("w", encoding="utf-8") as output:
        for path in paths:
            entry = load_json(path)
            if args.inflections_only:
                body = inflection_payload(entry, args.model)
            else:
                task = task_for(entry)
                body = response_payload(task, args.model, translation_only=is_translation_only(task))
            line = {"custom_id": path.name, "method": "POST", "url": "/v1/responses", "body": body}
            output.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"Prepared {len(paths)} requests. Uploading the batch file...", flush=True)
    uploaded = upload_batch_file(request_file, api_key)
    batch = api_json("POST", "/batches", api_key, {"input_file_id": uploaded["id"], "endpoint": "/v1/responses", "completion_window": "24h"})
    manifest = args.proposals.parent / f"batch_{batch['id']}.json"
    manifest.write_text(json.dumps({"batch_id": batch["id"], "status": batch.get("status"), "request_file": str(request_file), "count": len(paths)}, indent=2), encoding="utf-8")
    print(f"Submitted {len(paths)} requests as {batch['id']}. Check later with: python enrich_json.py batch-status --batch-id {batch['id']}")
    return 0


def batch_status(args: argparse.Namespace) -> int:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set.", file=sys.stderr)
        return 2
    batch = api_json("GET", f"/batches/{args.batch_id}", api_key)
    counts = batch.get("request_counts", {})
    print(json.dumps({"id": batch.get("id"), "status": batch.get("status"), "request_counts": counts, "errors": batch.get("errors"), "output_file_id": batch.get("output_file_id"), "error_file_id": batch.get("error_file_id")}, ensure_ascii=False, indent=2))
    return 0


def download_file(file_id: str, api_key: str) -> str:
    request = urllib.request.Request(API_BASE_URL + f"/files/{file_id}/content", headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def batch_collect(args: argparse.Namespace) -> int:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set.", file=sys.stderr)
        return 2
    batch = api_json("GET", f"/batches/{args.batch_id}", api_key)
    if batch.get("status") != "completed":
        print(f"Batch is {batch.get('status')}; there is nothing to collect yet.")
        return 1
    output_id = batch.get("output_file_id")
    if not output_id:
        print("Completed batch has no output file.", file=sys.stderr)
        return 1
    known = proposed_sources(args.proposals)
    added = 0
    failed = 0
    args.proposals.parent.mkdir(parents=True, exist_ok=True)
    with args.proposals.open("a", encoding="utf-8") as output, args.failures.open("a", encoding="utf-8") as failures:
        for line in download_file(output_id, api_key).splitlines():
            result = json.loads(line)
            source = result.get("custom_id")
            if not isinstance(source, str) or (source in known and not args.inflections_only):
                continue
            entry = load_json(args.source / source)
            task = task_for(entry)
            try:
                response = result.get("response") or {}
                if response.get("status_code") != 200:
                    raise ValueError(f"Batch request returned HTTP {response.get('status_code')}")
                model_response = json.loads(response_text(response["body"]))
                if args.inflections_only:
                    patch = inflection_patch(model_response)
                else:
                    patch = translation_patch(model_response) if "translations" in model_response else model_response
                patch = preserve_existing_values(entry, patch)
                validate_patch(entry, patch)
                output.write(json.dumps({"source": source, "task": task, "patch": patch}, ensure_ascii=False) + "\n")
                if not args.inflections_only:
                    known.add(source)
                added += 1
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                failures.write(json.dumps({"source": source, "task": task, "patch": None, "error": str(exc)}, ensure_ascii=False) + "\n")
                failed += 1
    print(f"Collected {added} proposals; {failed} were recorded as failures. Source JSONs were not changed.")
    return 0


def recover(args: argparse.Namespace) -> int:
    """Promote valid saved failures after discarding repeated source fields."""
    if not args.failures.exists():
        print(f"No failure file found at {args.failures}.")
        return 0
    known = proposed_sources(args.proposals)
    recovered = 0
    args.proposals.parent.mkdir(parents=True, exist_ok=True)
    with args.proposals.open("a", encoding="utf-8") as output, args.failures.open(encoding="utf-8") as failures:
        for line_number, line in enumerate(failures, start=1):
            try:
                record = json.loads(line)
                source = record["source"]
                patch = record["patch"]
                if source in known or not isinstance(patch, dict):
                    continue
                entry = load_json(args.source / source)
                patch = preserve_existing_values(entry, patch)
                validate_patch(entry, patch)
            except (json.JSONDecodeError, FileNotFoundError, KeyError, TypeError, ValueError) as exc:
                print(f"Line {line_number}: could not recover: {exc}", file=sys.stderr)
                continue
            output.write(json.dumps({"source": source, "task": record.get("task", {}), "patch": patch}, ensure_ascii=False) + "\n")
            known.add(source)
            recovered += 1
    print(f"Recovered {recovered} existing proposals without calling the API.")
    return 0


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def apply(args: argparse.Namespace) -> int:
    if not args.apply:
        print("Refusing to write. Re-run with --apply after reviewing the proposal file.", file=sys.stderr)
        return 2
    applied = 0
    with args.proposals.open(encoding="utf-8") as proposals:
        for line_number, line in enumerate(proposals, start=1):
            record = json.loads(line)
            path = args.source / record["source"]
            entry = load_json(path)
            patch = record["patch"]
            if args.inflections_only and (patch.get("new_definitions") or patch.get("definition_updates")):
                continue
            try:
                if args.inflections_only:
                    patch = preserve_existing_values(entry, patch)
                validate_patch(entry, patch)
                updated = merge(entry, patch)
            except (ValueError, KeyError) as exc:
                print(f"Line {line_number}: skipped {path.name}: {exc}", file=sys.stderr)
                continue
            with path.open("w", encoding="utf-8") as output:
                json.dump(updated, output, ensure_ascii=False, indent=4)
                output.write("\n")
            applied += 1
    print(f"Applied {applied} reviewed proposals to {args.source}.")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    common.add_argument("--proposals", type=Path, default=DEFAULT_PROPOSALS)

    propose_parser = subparsers.add_parser("propose", parents=[common])
    propose_parser.add_argument("--model", default="gpt-5.4-mini")
    propose_parser.add_argument("--limit", type=int, help="Process only the first N entries.")
    propose_parser.add_argument("--only", action="append", metavar="FILE", help="Process only this JSON filename; repeatable.")
    propose_parser.add_argument("--dry-run", action="store_true", help="List entries to process without calling the API.")
    propose_parser.add_argument("--timeout", type=int, default=60)
    propose_parser.add_argument("--delay", type=float, default=0.0)
    propose_parser.add_argument("--failures", type=Path, default=DEFAULT_FAILURES)
    propose_parser.set_defaults(handler=propose)

    apply_parser = subparsers.add_parser("apply", parents=[common])
    apply_parser.add_argument("--apply", action="store_true", help="Required before any source JSON is written.")
    apply_parser.add_argument("--inflections-only", action="store_true", help="Apply only inflection-only proposals; useful after an inflections batch.")
    apply_parser.set_defaults(handler=apply)

    recover_parser = subparsers.add_parser("recover", parents=[common])
    recover_parser.add_argument("--failures", type=Path, default=DEFAULT_FAILURES)
    recover_parser.set_defaults(handler=recover)

    batch_submit_parser = subparsers.add_parser("batch-submit", parents=[common])
    batch_submit_parser.add_argument("--model", default="gpt-5.4-mini")
    batch_submit_parser.add_argument("--limit", type=int, help="Submit only the first N pending entries.")
    batch_submit_parser.add_argument("--inflections-only", action="store_true", help="Submit only missing inflections, even for entries that already have a proposal.")
    batch_submit_parser.set_defaults(handler=batch_submit)

    batch_status_parser = subparsers.add_parser("batch-status")
    batch_status_parser.add_argument("--batch-id", required=True)
    batch_status_parser.set_defaults(handler=batch_status)

    batch_collect_parser = subparsers.add_parser("batch-collect", parents=[common])
    batch_collect_parser.add_argument("--batch-id", required=True)
    batch_collect_parser.add_argument("--failures", type=Path, default=DEFAULT_FAILURES)
    batch_collect_parser.add_argument("--inflections-only", action="store_true", help="Collect a batch created with --inflections-only.")
    batch_collect_parser.set_defaults(handler=batch_collect)
    return result


if __name__ == "__main__":
    arguments = parser().parse_args()
    raise SystemExit(arguments.handler(arguments))
