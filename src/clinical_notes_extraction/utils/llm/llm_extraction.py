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
- `frozen=True` keeps it stateless, and therefore both trivially testable and
  safe to share across threads: concurrent notes never contend, since every
  call writes its own file.

Conventions:
- .replace() injection, fixed content first, note last (literal JSON braces).
- `results_dir` is the fully-resolved run folder, built once in the notebook,
  so re-running a grid never overwrites a previous run's outputs.
- One JSON file per (note, model, strategy) -> resumable runs.
- Invalid output is logged to a separate errors/ tree with the raw response,
  not raised.

Record layout (identical for every status, so the run notebook can build a
DataFrame straight from a list of records):
- output   -- the Pydantic-validated dict; THE ONLY FIELD THE EVALUATION READS.
- raw      -- the model's message content before cleaning and parsing.
- response -- the rest of the Ollama payload, verbatim minus the message.
- usage    -- token counts, latency and the context-overflow flag.
- error    -- failure message, None on success.

Failure policy (mirrored by the run notebook):
- Model-side and infrastructure failures are RETURNED as a record and written
  to errors/, so one bad note never kills a multi-hour grid.
- Connection errors, timeouts and prompt-assembly bugs are RAISED, because
  they invalidate every remaining cell: failing loudly is the correct
  behaviour.
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import requests
from pydantic import ValidationError

from clinical_notes_extraction.utils.llm.schemas import ExtractionOutput

# Fallback used when the caller does not pin how long the model stays resident.
DEFAULT_KEEP_ALIVE = "5m"

# Pulling a 70b into VRAM can take minutes; the per-call timeout is sized for
# generation, not for a cold load, hence a separate and much larger budget.
DEFAULT_LOAD_TIMEOUT_SECONDS = 900

# Best-effort call whose failure must never interrupt the run.
UNLOAD_TIMEOUT_SECONDS = 30

# Cooldown before the single OOM retry, giving the shared GPU time to drain.
OOM_RETRY_SLEEP_SECONDS = 30

# Error bodies are truncated before being persisted: enough to diagnose, short
# enough to keep the record readable.
ERROR_BODY_CHARS = 500

NANOSECONDS_PER_SECOND = 1e9

# Connect timeout kept short so a down server fails fast, independently of the
# much larger read budget that generation needs.
CONNECT_TIMEOUT_SECONDS = 10


# `eq=False` keeps the instance unhashable-by-value: `ollama_config` is a dict,
# so the __hash__ generated for a frozen dataclass would raise on any hash().
@dataclass(frozen=True, eq=False)
class ExtractionRunner:
    """Runs extraction cells for one fixed (model, strategy) combination."""

    model: str
    strategy: str
    role: str
    template: str
    expected_template: str
    # Fully-resolved run folder (timestamped, built once in the notebook).
    # Nothing is appended to it here, so every path below hangs off a single,
    # caller-owned root.
    results_dir: Path
    ollama_config: dict
    # Resolved once at construction so a run started before midnight keeps
    # writing to the same folder. Pass an earlier date to resume that run.
    run_date: str = field(default_factory=lambda: date.today().isoformat())
    debug_prompt: bool = False

    def __post_init__(self) -> None:
        """Fail at construction, not on the first note of a multi-hour grid.

        The three required options are the ones whose absence corrupts the
        experiment rather than crashing it:
        - num_ctx: Ollama defaults to 2048-4096 and silently truncates the
          START of the prompt on overflow, dropping role and expected_template.
          The run completes, the scores are bad, and nothing explains why.
        - temperature: any value above 0 turns strategy comparison into a
          measurement of sampling noise.
        - seed: greedy decoding alone does not guarantee reproducibility, and
          an unreproducible run cannot be defended.
        """
        missing = {"url", "options", "timeout_seconds"} - self.ollama_config.keys()
        if missing:
            raise ValueError(f"ollama_config missing keys: {sorted(missing)}")

        missing_options = {"num_ctx", "temperature", "seed"} - self.ollama_config["options"].keys()
        if missing_options:
            raise ValueError(
                f"ollama_config['options'] missing keys: {sorted(missing_options)}"
            )

    @property
    def safe_model(self) -> str:
        """Model name usable as a directory (medgemma:27b -> medgemma_27b)."""
        return self.model.replace(":", "_").replace("/", "_")

    @property
    def keep_alive(self) -> str | int:
        """How long the model stays in VRAM after a call.

        Explicit because the Ollama default keeps the previous model resident
        when the eval loop switches models -> OOM.
        """
        return self.ollama_config.get("keep_alive", DEFAULT_KEEP_ALIVE)

    @property
    def num_ctx(self) -> int:
        """Context window, guaranteed present by __post_init__."""
        return self.ollama_config["options"]["num_ctx"]

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def result_path(self, note_id: str) -> Path:
        """Cache path for a valid extraction: <model>/<strategy>/<note>.json.

        Keeping errors out of this tree means a glob over
        <model>/<strategy>/*.json returns valid records only, with no filtering.
        """
        return self.results_dir / self.safe_model / self.strategy / f"{note_id}.json"

    def error_path(self, note_id: str) -> Path:
        """Cache path for a failed extraction, under the model's errors/ tree."""
        return (
            self.results_dir
            / self.safe_model
            / "errors"
            / self.strategy
            / f"{note_id}.json"
        )

    def prompt_path(self, note_id: str) -> Path:
        """Path for the dumped prompt of one cell, when debug_prompt is on."""
        return (
            self.results_dir
            / self.safe_model
            / "prompts"
            / self.strategy
            / f"{note_id}.txt"
        )

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

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

    @staticmethod
    def clean_output(raw: str) -> str:
        """Normalize model output before JSON parsing.

        Idempotent on already-clean JSON: each substitution is a no-op when its
        pattern is absent, so output from JSON-conformant models passes through
        byte-identical. Only reasoning/markdown-wrapping models (e.g.
        deepseek-r1) are affected -- they wrap the object in ```json fences
        and/or precede it with a <think>...</think> block, both of which break
        json.loads.

        Splitting on the closing tag rather than matching the pair also handles
        the orphan case, where the opening <think> is missing from the returned
        content and a paired regex would leave the whole block in place.
        """
        raw = raw.rsplit("</think>", 1)[-1]
        raw = re.sub(r"```(?:json)?\s*", "", raw)  # \s* means every fence is matched
        return raw.strip()

    # ------------------------------------------------------------------
    # Ollama
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Preload the model into VRAM. Call once before a cell's note loop.

        Without this the first note pays the cold-load time against
        `timeout_seconds`, which is sized for generation: on a 70b that alone
        can exhaust the budget and raise a Timeout that aborts the whole grid.
        An empty message list loads the model without generating anything.
        """
        response = requests.post(
            f"{self.ollama_config['url']}/api/chat",
            json={
                "model": self.model,
                "messages": [],
                "keep_alive": self.keep_alive,
                # Must match the generation call: options that change the
                # runner (num_ctx) trigger a reload, wasting the preload.
                "options": self.ollama_config["options"],
            },
            timeout=self.ollama_config.get(
                "load_timeout_seconds", DEFAULT_LOAD_TIMEOUT_SECONDS
            ),
        )
        if not response.ok:
            raise RuntimeError(
                f"Ollama failed to load {self.model} "
                f"({response.status_code}): {response.text[:ERROR_BODY_CHARS]}"
            )

    def unload(self) -> None:
        """Frees the model from VRAM. Call between models in the eval loop."""
        try:
            requests.post(
                f"{self.ollama_config['url']}/api/chat",
                json={"model": self.model, "messages": [], "keep_alive": 0},
                timeout=UNLOAD_TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            pass  # best-effort; never break the run over a failed unload

    def call_ollama(self, user_prompt: str, _retry: bool = True) -> dict:
        """Single chat call, returning the FULL payload.

        The payload is returned rather than just the message content because
        the counters it carries (prompt_eval_count, eval_count, durations) are
        per-call telemetry that cannot be recovered afterwards: they feed the
        cost table and the context-overflow check. Parsing stays the caller's
        job so malformed output can still be persisted.

        - num_ctx (in options) must be set explicitly -- see __post_init__.
        - 8192 covers prompt + note + example + output; KV-cache VRAM grows
          linearly with it, and with num_ctx * OLLAMA_NUM_PARALLEL under
          concurrency.
        - On CUDA OOM, unloads and retries once: the shared GPU may just have
          been busy.
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
                "keep_alive": self.keep_alive,
                "options": self.ollama_config["options"],
            },
            timeout=(CONNECT_TIMEOUT_SECONDS, self.ollama_config["timeout_seconds"]),
        )

        if not response.ok:
            body = response.text[:ERROR_BODY_CHARS]
            if _retry and "out of memory" in body.lower():
                self.unload()
                time.sleep(OOM_RETRY_SLEEP_SECONDS)
                return self.call_ollama(user_prompt, _retry=False)
            raise RuntimeError(f"Ollama {response.status_code}: {body}")

        # Ollama can answer 200 with an error payload instead of a message
        # (model not pulled, broken chat template). Indexing straight into
        # ["message"]["content"] would raise KeyError, which extract() does not
        # catch -- so an infrastructure failure would abort the grid instead of
        # landing in errors/ as a RuntimeError like every other one.
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"Ollama error: {payload['error']}")
        if "message" not in payload:
            raise RuntimeError(
                f"Unexpected Ollama response: {json.dumps(payload)[:ERROR_BODY_CHARS]}"
            )

        return payload

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    @staticmethod
    def _seconds(nanoseconds: int | None) -> float | None:
        """Ollama reports every duration in nanoseconds."""
        return round(nanoseconds / NANOSECONDS_PER_SECOND, 3) if nanoseconds else None

    def usage_from(self, payload: dict) -> dict:
        """Token counts and latency for one call.

        context_overflow flags the notes whose prompt plus completion filled
        the window. It is a >= comparison because on overflow Ollama reports
        the count AFTER truncation, so an exhausted window is the only visible
        symptom of the silent prompt cut described in __post_init__.
        """
        prompt_tokens = payload.get("prompt_eval_count")
        completion_tokens = payload.get("eval_count")
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
        eval_seconds = self._seconds(payload.get("eval_duration"))

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "num_ctx": self.num_ctx,
            "context_overflow": total_tokens >= self.num_ctx,
            "total_duration_s": self._seconds(payload.get("total_duration")),
            "load_duration_s": self._seconds(payload.get("load_duration")),
            "prompt_eval_duration_s": self._seconds(payload.get("prompt_eval_duration")),
            "eval_duration_s": eval_seconds,
            "tokens_per_second": (
                round(completion_tokens / eval_seconds, 2)
                if completion_tokens and eval_seconds
                else None
            ),
        }

    # ------------------------------------------------------------------
    # Cell
    # ------------------------------------------------------------------

    def extract(self, note_id: str, note_text: str, examples: str = "") -> dict:
        """Run one cell, validate with Pydantic, persist to disk.

        - Skips the call if a result exists in either tree of this run folder.
        - Delete the file under errors/ to force a re-run.
        - Thread-safe: no shared state, and the target path is unique per cell.
        """
        out_path = self.result_path(note_id)
        err_path = self.error_path(note_id)
        for cached in (out_path, err_path):
            if cached.exists():
                return json.loads(cached.read_text(encoding="utf-8"))

        prompt = self.build_prompt(note_id, note_text, examples)
        if self.debug_prompt:
            dump_path = self.prompt_path(note_id)
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_text(prompt, encoding="utf-8")

        # Every key is initialised so the record schema is identical across
        # statuses, and a list of records maps straight onto a DataFrame.
        record = {
            "note_id": note_id,
            "model": self.model,
            "strategy": self.strategy,
            "run_date": self.run_date,
            "status": None,
            "output": None,
            "raw": None,
            "response": None,
            "usage": None,
            "error": None,
        }

        try:
            payload = self.call_ollama(prompt)
            # Captured before parsing, so they survive a malformed answer.
            record["raw"] = payload["message"]["content"]
            record["response"] = {k: v for k, v in payload.items() if k != "message"}
            record["usage"] = self.usage_from(payload)

            validated = ExtractionOutput.model_validate(
                json.loads(self.clean_output(record["raw"]))
            )
            record["status"] = "ok"
            record["output"] = validated.model_dump()
            target = out_path
        except (json.JSONDecodeError, ValidationError) as err:
            # Model-side failure (recall = 0): the model answered but the
            # output is malformed or off-schema. Raw is kept -- only evidence
            # of HOW the model failed, unrecoverable afterwards.
            record["status"] = "invalid"
            record["error"] = str(err)
            target = err_path
        except RuntimeError as err:
            # Infrastructure failure (non-2xx, error payload, exhausted OOM
            # retry): distinct from "invalid" so failure types stay separable
            # in analysis, and one bad note doesn't kill a multi-hour grid.
            # Connection errors and timeouts are deliberately NOT caught -- if
            # the server is fully down, stopping loudly is the correct
            # behaviour. raw/response/usage stay None: the call never returned.
            record["status"] = "error"
            record["error"] = str(err)
            target = err_path

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return record