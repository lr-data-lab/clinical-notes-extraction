"""Span utilities and entity-level evaluation metrics for medication extraction.

Shared by ``run_extraction.py`` (span verification/localisation) and by both
evaluation notebooks (train/val model selection and final test report), which
is why this module lives in ``utils/``.

Evaluation design
-----------------
Extractions are compared to the ground-truth JSON at the entity (medication
mention) level, using character spans in the source note. Two matching
criteria are computed independently:

* **exact**   — predicted span boundaries are identical to the gold span.
* **relaxed** — each boundary may deviate by up to 10% of the gold span length
  (at least 1 character), i.e. small over/under-extensions still count.

For each criterion we report precision, recall and F1, micro-averaged across
all notes of a split. Matching is greedy and one-to-one: each gold entity can
be matched by at most one prediction and vice versa.
"""

import math

RELAXED_TOLERANCE = 0.10  # fraction of the gold span length allowed per boundary


# ---------------------------------------------------------------------------
# Span localisation
# ---------------------------------------------------------------------------
def locate_spans(note_text: str, span_texts: list[str]) -> list[dict]:
    """Locate each verbatim span inside the note and return char offsets.

    Handles repeated spans (e.g. the same drug mentioned twice) by resuming the
    search after the last occurrence found for that exact text. Spans not found
    verbatim in the note are returned with ``start = end = None`` and
    ``verified = False`` — they count as model errors downstream, never as
    silent drops.
    """
    cursor: dict[str, int] = {}  # per-span-text search position
    located = []
    for span in span_texts:
        start = note_text.find(span, cursor.get(span, 0))
        if start == -1:
            located.append({"span": span, "start": None, "end": None, "verified": False})
            continue
        end = start + len(span)
        cursor[span] = end
        located.append({"span": span, "start": start, "end": end, "verified": True})
    return located


# ---------------------------------------------------------------------------
# Matching criteria
# ---------------------------------------------------------------------------
def _is_exact_match(pred: dict, gold: dict) -> bool:
    return pred["start"] == gold["start"] and pred["end"] == gold["end"]


def _is_relaxed_match(pred: dict, gold: dict) -> bool:
    """True if both boundaries are within 10% of the gold span length."""
    tolerance = max(1, math.ceil(RELAXED_TOLERANCE * (gold["end"] - gold["start"])))
    return (
        abs(pred["start"] - gold["start"]) <= tolerance
        and abs(pred["end"] - gold["end"]) <= tolerance
    )


_CRITERIA = {"exact": _is_exact_match, "relaxed": _is_relaxed_match}


# ---------------------------------------------------------------------------
# Per-note evaluation
# ---------------------------------------------------------------------------
def evaluate_note(predicted: list[dict], gold: list[dict], criterion: str) -> dict:
    """Return TP/FP/FN counts for one note under the given matching criterion.

    Both ``predicted`` and ``gold`` are lists of dicts with integer ``start``
    and ``end`` keys. Predictions with unverified spans (start is None) can
    never match and therefore count as false positives — a model that invents
    text not present in the note is penalised, by design.
    """
    match_fn = _CRITERIA[criterion]
    matched_gold: set[int] = set()

    tp = 0
    for pred in predicted:
        if pred.get("start") is None:
            continue  # unverifiable span -> stays an FP
        for i, g in enumerate(gold):
            if i in matched_gold:
                continue
            if match_fn(pred, g):
                matched_gold.add(i)
                tp += 1
                break

    return {"tp": tp, "fp": len(predicted) - tp, "fn": len(gold) - tp}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def micro_average(note_results: list[dict]) -> dict:
    """Aggregate per-note TP/FP/FN counts into micro-averaged P / R / F1."""
    tp = sum(r["tp"] for r in note_results)
    fp = sum(r["fp"] for r in note_results)
    fn = sum(r["fn"] for r in note_results)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def evaluate_split(predictions: dict[str, list[dict]], ground_truth: dict[str, list[dict]]) -> dict:
    """Evaluate one (model, strategy) run over a whole split.

    Parameters
    ----------
    predictions : mapping note_id -> list of predicted entities (with start/end)
    ground_truth : mapping note_id -> list of gold entities (with start/end)

    Returns a flat dict with both criteria, e.g.::

        {"exact_precision": ..., "exact_recall": ..., "exact_f1": ...,
         "relaxed_precision": ..., "relaxed_recall": ..., "relaxed_f1": ..., ...}
    """
    metrics: dict[str, float] = {}
    for criterion in _CRITERIA:
        note_results = [
            evaluate_note(predictions[note_id], ground_truth[note_id], criterion)
            for note_id in predictions
        ]
        for name, value in micro_average(note_results).items():
            metrics[f"{criterion}_{name}"] = value
    return metrics
