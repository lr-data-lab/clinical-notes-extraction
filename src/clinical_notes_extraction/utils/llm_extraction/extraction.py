"""LLM extraction via direct Ollama HTTP calls.

Pure functions: all prompt content (role, strategy template, expected
template, examples) and runtime settings (Ollama URL, options, timeout)
are received as parameters. File loading, paths and config live in the
run notebooks.

- Prompts use .replace() injection (fixed content first, variable content
  last) to avoid clashes with literal JSON braces.
- One JSON result file per (note, model, strategy) cell -> resumable runs.
- Invalid model output is a logged result, not a crash.
"""

import json
from pathlib import Path

import requests
from pydantic import ValidationError

from clinical_notes_extraction.utils.schema import ExtractionOutput


def build_prompt(
    template: str,
    expected_template: str,
    note_text: str,
    examples: str = "",
) -> str:
    """Assemble the final prompt. Injection order: fixed content, then note."""
    prompt = template.replace("{EXPECTED_TEMPLATE}", expected_template)
    prompt = prompt.replace("{EXAMPLES}", examples)
    prompt = prompt.replace("{NOTE_TEXT}", note_text)
    return prompt


def call_ollama(
    model: str,
    system_prompt: str,
    user_prompt: str,
    ollama_url: str,
    options: dict,
    timeout: int,
) -> dict:
    """Single chat call. JSON mode; options (temperature, num_ctx) from config.

    num_ctx = context window Ollama allocates for this call: max tokens the
    model can see at once, counting FULL INPUT (system prompt + strategy
    template + expected_template + examples + note text) PLUS the generated
    output. It is set explicitly because Ollama's default is short (2048-4096
    regardless of the model's maximum) and overflow is handled by SILENT
    truncation of the prompt's beginning (role/template lost, no error raised),
    which would degrade output undetectably. 8192 tokens (~30K chars) is ample
    for medication sections + fixed prompt + 2 dynamic examples; raise it in
    config if the worst-case check in the run notebook gets close to the limit
    (KV-cache VRAM cost grows linearly with num_ctx, negligible on 127 GB).
    """
    response = requests.post(
        f"{ollama_url}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": options,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return json.loads(response.json()["message"]["content"])


def result_path(results_dir: Path, note_id: str, model: str, strategy: str) -> Path:
    """Deterministic cache path for one experiment cell."""
    safe_model = model.replace(":", "_").replace("/", "_")
    return results_dir / safe_model / strategy / f"{note_id}.json"


def extract_note(
    note_id: str,
    note_text: str,
    model: str,
    strategy: str,
    role: str,
    template: str,
    expected_template: str,
    results_dir: Path,
    ollama_config: dict,
    examples: str = "",
) -> dict:
    """Run one extraction cell, validate with Pydantic, persist to disk.

    Skips the call if the result file already exists (resume support).
    """
    out_path = result_path(results_dir, note_id, model, strategy)
    if out_path.exists():
        return json.loads(out_path.read_text(encoding="utf-8"))

    prompt = build_prompt(template, expected_template, note_text, examples)

    record = {"note_id": note_id, "model": model, "strategy": strategy}

    try:
        raw = call_ollama(
            model,
            role,
            prompt,
            ollama_url=ollama_config["url"],
            options=ollama_config["options"],
            timeout=ollama_config["timeout_seconds"],
        )
        validated = ExtractionOutput.model_validate(raw)
        record["status"] = "ok"
        record["output"] = validated.model_dump()
    except (json.JSONDecodeError, ValidationError) as err:
        # Invalid structure counts as a failed cell in evaluation (recall = 0)
        record["status"] = "invalid"
        record["error"] = str(err)
        record["output"] = None

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record