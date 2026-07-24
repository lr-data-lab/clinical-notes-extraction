"""LLM extraction via direct Ollama HTTP calls.

`ExtractionRunner` binds the invariant config of one (model, strategy) cell;
only the note and its examples vary per call. Paths, file loading and config
live in the run notebooks.

Why a class:
- The 7 config parameters are constant across a run; only
  note_id/note_text/examples change, so binding them once shortens the call
  inside the loop.
- Config is validated once at construction, not re-passed per iteration.
- Path construction lives in a single place, so model-name sanitisation
  cannot drift between call sites.
- `frozen=True` keeps it stateless, and therefore as testable as plain
  functions.

Conventions:
- .replace() injection, fixed content first, note last (literal JSON braces).
- Results are written under a per-run date folder, so re-running a grid never
  overwrites a previous run's outputs.
- One JSON file per (note, model, strategy) -> resumable runs.
- Invalid output is logged to a separate errors/ tree with the raw response,
  not raised.
"""

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import re

import requests
from pydantic import ValidationError

from clinical_notes_extraction.utils.llm.schemas import ExtractionOutput


@dataclass(frozen=True)
class ExtractionRunner:
    """Runs extraction cells for one fixed (model, strategy) combination."""

    model: str
    strategy: str
    role: str
    template: str
    expected_template: str
    results_dir: Path
    ollama_config: dict
    # Resolved once at construction so a run started before midnight keeps
    # writing to the same folder. Pass an earlier date to resume that run.
    run_date: str = field(default_factory=lambda: date.today().isoformat())
    debug_prompt: bool = False

    @property
    def safe_model(self) -> str:
        """Model name usable as a directory (medgemma:27b -> medgemma_27b)."""
        return self.model.replace(":", "_").replace("/", "_")

    @property
    def run_dir(self) -> Path:
        """Root of this run: results_dir/<YYYY-MM-DD>."""
        return self.results_dir / self.run_date

    def result_path(self, note_id: str) -> Path:
        """Cache path for a valid extraction."""
        return self.run_dir / self.safe_model / self.strategy / f"{note_id}.json"

    def error_path(self, note_id: str) -> Path:
        """Cache path for a failed extraction, under the model's errors/ tree."""
        return (
            self.run_dir
            / self.safe_model
            / "errors"
            / self.strategy
            / f"{note_id}.json"
        )

    def build_prompt(self, note_id: str, note_text: str, examples: str = "") -> str:
            """Assemble the final prompt: fixed content first, note last."""
            prompt = self.template.replace("{EXPECTED_TEMPLATE}", self.expected_template)
            prompt = prompt.replace("{EXAMPLES}", examples)
            prompt = prompt.replace("{NOTE_ID}", note_id)
            prompt = prompt.replace("{NOTE_TEXT}", note_text)
            # Unreplaced placeholders reach the model silently and corrupt the run.
            leftover = re.findall(r"\{[A-Z_]+\}", prompt)
            if leftover:
                raise ValueError(f"Unreplaced placeholders in {self.strategy}: {leftover}")
            return prompt

    def call_ollama(self, user_prompt: str, _retry: bool = True) -> str:
        """Single chat call.

        - Returns raw message content; parsing is the caller's job so
          malformed output can still be persisted.
        - num_ctx (in options) must be set explicitly: Ollama defaults to
          2048-4096 and silently truncates the START of the prompt on
          overflow, dropping role/template with no error.
        - 8192 covers prompt + note + example + output; KV-cache VRAM
          grows linearly with it.
        - keep_alive controls how long the model stays in VRAM after the
          call. Explicit here because the default (5m) keeps the previous
          model resident when the eval loop switches models -> OOM.
        - On CUDA OOM, unloads and retries once: the shared GPU may just
          have been busy.
        """
        response = requests.post(
            f"{self.ollama_config['url']}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.role},
                    {"role": "user", "content": user_prompt},
                ],
                "format": "json",
                "stream": False,
                "keep_alive": self.ollama_config.get("keep_alive", "5m"),
                "options": self.ollama_config["options"],
            },
            timeout=self.ollama_config["timeout_seconds"],
        )

        if not response.ok:
            body = response.text[:500]
            if _retry and "out of memory" in body.lower():
                self.unload()
                time.sleep(30)
                return self.call_ollama(user_prompt, _retry=False)
            raise RuntimeError(f"Ollama {response.status_code}: {body}")

        return response.json()["message"]["content"]


    def unload(self) -> None:
            """Frees the model from VRAM. Call between models in the eval loop."""
            try:
                requests.post(
                    f"{self.ollama_config['url']}/api/chat",
                    json={"model": self.model, "messages": [], "keep_alive": 0},
                    timeout=30,
                )
            except requests.RequestException:
                pass  # best-effort; never break the run over a failed unload

    def extract(self, note_id: str, note_text: str, examples: str = "") -> dict:
        """Run one cell, validate with Pydantic, persist to disk.

        - Skips the call if a result exists in either tree of this run_date.
        - Delete the file under errors/ to force a re-run.
        """
        out_path = self.result_path(note_id)
        err_path = self.error_path(note_id)
        for cached in (out_path, err_path):
            if cached.exists():
                return json.loads(cached.read_text(encoding="utf-8"))

        prompt = self.build_prompt(note_id, note_text, examples)
        if self.debug_prompt:
            print(f"--- PROMPT [{self.model} | {self.strategy} | {note_id} ---")
            print(prompt)
            print("--- END PROMPT ---")

        record = {
            "note_id": note_id,
            "model": self.model,
            "strategy": self.strategy,
            "run_date": self.run_date,
        }
        raw = None

        try:
            raw = self.call_ollama(prompt)
            validated = ExtractionOutput.model_validate(json.loads(raw))
            record["status"] = "ok"
            record["output"] = validated.model_dump()
            target = out_path
        except (json.JSONDecodeError, ValidationError) as err:
            # Failed cell (recall = 0). Raw output is kept: only evidence of
            # HOW the model failed, unrecoverable afterwards.
            record["status"] = "invalid"
            record["error"] = str(err)
            record["output"] = None
            record["raw"] = raw
            target = err_path

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record