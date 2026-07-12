"""Run LLM extraction of "Medications on Admission" over a data split.

Inference goes directly through the local Ollama server (PhysioNet DUA: no
cloud APIs), with the role prompt in the system channel and JSON output
enforced via Ollama's ``format="json"`` option. Every extracted span must be a
verbatim substring of the note; spans are verified and localised to character
offsets after generation, and non-verbatim outputs are kept but flagged so the
evaluation penalises them as false positives.

Prompting strategies
--------------------
* ``zero_shot`` — role + task instructions + expected output schema. No
  examples of any kind.
* ``few_shot``  — adds 2 curated examples drawn from the POPULATION, outside
  the 32-note annotated sample (``config/few_shot_examples.json``). Because
  the examples are not sample notes, there is no leakage and no leave-one-out
  is needed.
* ``dynamic``   — adds the medoid (central note) of the cluster the incoming
  note belongs to, precomputed by ``notebooks/08_cluster_medoids.ipynb`` and
  stored in ``config/cluster_medoids.json``. Medoids are also population
  notes, never sample notes.

Experiment phases
-----------------
Phase 1 — model/prompt selection on train/val (all combinations)::

    python scripts/run_extraction.py --split train_val --strategies zero_shot few_shot dynamic

Phase 2 — final run of the winning combination on test (once)::

    python scripts/run_extraction.py --split test --models <best> --strategies <best>

If ``--models`` is omitted, the hardware-vetted list written by
``download_models.py`` (``config/runnable_models.json``) is used.

Outputs: ``results/<split>/<model>/<strategy>/<note_id>.json`` and a run log
at ``results/<split>/run_log.csv``. Runs are resumable: existing output files
are skipped.
"""

import argparse
import json
import logging
import time
from pathlib import Path

import pandas as pd
import requests
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from clinical_notes_extraction.utils.evaluation import locate_spans

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths and constants — adjust to the project layout if needed.
# ---------------------------------------------------------------------------
DATA_DIR = Path("data/splits")                 # train_val.csv / test.csv (notebook 07)
PROMPTS_DIR = Path("prompts/admission")        # role.yml, zero_shot_prompt.yml, ...
FEW_SHOT_EXAMPLES_FILE = Path("config/few_shot_examples.json")
CLUSTER_MEDOIDS_FILE = Path("config/cluster_medoids.json")
RUNNABLE_MODELS_FILE = Path("config/runnable_models.json")
RESULTS_DIR = Path("results")

OLLAMA_CHAT_URL = "http://localhost:11435/api/chat"
REQUEST_TIMEOUT_S = 600        # generous: long notes on CPU can be slow
TEMPERATURE = 0.0              # deterministic decoding for reproducibility
NOTE_PLACEHOLDER = "{note_text}"      # placeholder token inside the prompt YAMLs
EXAMPLES_PLACEHOLDER = "{examples}"   # placeholder token for the examples block


# ---------------------------------------------------------------------------
# Output schema — the contract the LLM must honour.
# ---------------------------------------------------------------------------
class ExtractedMedication(BaseModel):
    """One medication mention. ``span`` must be verbatim text from the note."""

    model_config = ConfigDict(extra="allow")  # tolerate extra fields (dosage, route, ...)

    span: str


class ExtractionOutput(BaseModel):
    """Top-level JSON object the model is instructed to return."""

    medications: list[ExtractedMedication]


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------
def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def format_examples_block(examples: list[dict]) -> str:
    """Render annotated examples as text to inject into the user prompt.

    Each example dict must have ``text`` (the note excerpt) and ``medications``
    (the gold JSON output). json.dumps produces literal braces, which is why
    prompt rendering uses ``str.replace`` and never ``str.format``.
    """
    blocks = []
    for i, ex in enumerate(examples, start=1):
        output = json.dumps({"medications": ex["medications"]}, indent=2)
        blocks.append(f"### Example {i}\nNote:\n{ex['text']}\n\nExpected output:\n{output}")
    return "\n\n".join(blocks)


def build_user_prompt(prompt_cfg: dict, note_text: str, examples: list[dict]) -> str:
    """Assemble the user-channel prompt for one note.

    Rendering uses ``str.replace`` (not ``str.format``) because the expected
    output schema and the example outputs contain literal JSON braces.
    """
    prompt = prompt_cfg["prompt"]
    if EXAMPLES_PLACEHOLDER in prompt:
        prompt = prompt.replace(EXAMPLES_PLACEHOLDER, format_examples_block(examples))
    prompt = prompt.replace(NOTE_PLACEHOLDER, note_text)
    return prompt


def select_examples(strategy: str, note: pd.Series,
                    few_shot_pool: list[dict], medoids: dict[str, dict]) -> list[dict]:
    """Return the examples for this note according to the prompting strategy."""
    if strategy == "zero_shot":
        return []
    if strategy == "few_shot":
        # Fixed pool: 2 curated population examples, external to the sample.
        return few_shot_pool
    if strategy == "dynamic":
        # The note's cluster is known from the clustering step (metadata column);
        # its medoid — the population note closest to the cluster centroid — is
        # the single, maximally representative example for that cluster.
        return [medoids[str(note["cluster"])]]
    raise ValueError(f"Unknown strategy: {strategy}")


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
def call_ollama(model: str, system_prompt: str, user_prompt: str) -> str:
    """Send one chat request to the local Ollama server and return the raw content."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": "json",  # constrains decoding to valid JSON
        "options": {"temperature": TEMPERATURE},
    }
    response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=REQUEST_TIMEOUT_S)
    response.raise_for_status()
    return response.json()["message"]["content"]


def extract_note(note_text: str, model: str, system_prompt: str, user_prompt: str) -> dict:
    """Run extraction on one note; validate, verify and localise spans.

    Returns a result dict with the medication list plus bookkeeping flags:
    ``json_valid`` (Pydantic validation passed) and per-medication
    ``verified`` (span found verbatim in the note).
    """
    raw = call_ollama(model, system_prompt, user_prompt)

    try:
        parsed = ExtractionOutput.model_validate_json(raw)
    except ValidationError as exc:
        # Invalid JSON structure is a model failure, recorded — not hidden.
        return {"medications": [], "json_valid": False, "raw_output": raw,
                "validation_error": str(exc)}

    # Verify the verbatim requirement and attach character offsets.
    located = locate_spans(note_text, [m.span for m in parsed.medications])
    medications = []
    for med, loc in zip(parsed.medications, located):
        entry = med.model_dump()
        entry.update(loc)  # start / end / verified
        medications.append(entry)

    return {"medications": medications, "json_valid": True}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def load_models_from_config() -> list[str]:
    """Default model list: whatever the hardware check deemed runnable."""
    if not RUNNABLE_MODELS_FILE.exists():
        raise FileNotFoundError(
            f"{RUNNABLE_MODELS_FILE} not found. Run scripts/download_models.py first, "
            "or pass --models explicitly."
        )
    with open(RUNNABLE_MODELS_FILE) as f:
        return json.load(f)["models"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["train_val", "test"], required=True)
    parser.add_argument("--models", nargs="+", default=None,
                        help="Ollama model tags. Defaults to config/runnable_models.json.")
    parser.add_argument("--strategies", nargs="+", required=True,
                        choices=["zero_shot", "few_shot", "dynamic"])
    args = parser.parse_args()

    models = args.models or load_models_from_config()
    df = pd.read_csv(DATA_DIR / f"{args.split}.csv")

    # Role goes to the system channel; task prompts to the user channel.
    system_prompt = load_yaml(PROMPTS_DIR / "role.yml")["role"]
    prompt_cfgs = {
        "zero_shot": load_yaml(PROMPTS_DIR / "zero_shot_prompt.yml"),
        "few_shot": load_yaml(PROMPTS_DIR / "few_shot_prompt.yml"),
        "dynamic": load_yaml(PROMPTS_DIR / "dynamic_prompt.yml"),
    }

    with open(FEW_SHOT_EXAMPLES_FILE) as f:
        few_shot_pool = json.load(f)
    with open(CLUSTER_MEDOIDS_FILE) as f:
        medoids = json.load(f)

    log_rows = []
    for model in models:
        for strategy in args.strategies:
            out_dir = RESULTS_DIR / args.split / model.replace(":", "_") / strategy
            out_dir.mkdir(parents=True, exist_ok=True)

            for _, note in df.iterrows():
                out_file = out_dir / f"{note['note_id']}.json"
                if out_file.exists():
                    continue  # resumable runs

                examples = select_examples(strategy, note, few_shot_pool, medoids)
                user_prompt = build_user_prompt(prompt_cfgs[strategy], note["text"], examples)

                t0 = time.time()
                error = None
                try:
                    result = extract_note(note["text"], model, system_prompt, user_prompt)
                except Exception as exc:  # noqa: BLE001 — log and continue the sweep
                    result = {"medications": [], "json_valid": False}
                    error = str(exc)
                elapsed = time.time() - t0

                result["note_id"] = note["note_id"]
                with open(out_file, "w") as f:
                    json.dump(result, f, indent=2)

                n_meds = len(result["medications"])
                n_unverified = sum(1 for m in result["medications"] if not m["verified"])
                log_rows.append({
                    "model": model, "strategy": strategy, "note_id": note["note_id"],
                    "n_extracted": n_meds, "n_unverified_spans": n_unverified,
                    "json_valid": result["json_valid"], "seconds": round(elapsed, 1),
                    "error": error,
                })
                logger.info("[%s | %s] %s: %d meds (%d unverified) in %.1fs%s",
                            model, strategy, note["note_id"], n_meds, n_unverified,
                            elapsed, f" ERROR: {error}" if error else "")

    pd.DataFrame(log_rows).to_csv(RESULTS_DIR / args.split / "run_log.csv", index=False)
    logger.info("Done. Results in %s", RESULTS_DIR / args.split)


if __name__ == "__main__":
    main()
