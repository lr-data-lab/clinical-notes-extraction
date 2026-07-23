"""Span-level evaluation against ground truth.

Unit of evaluation: the span record (field, start, end).
Matching is greedy one-to-one and restricted to the same field.

Criteria:
- exact: identical start and end (implies identical text);
- relaxed: each boundary may deviate up to 10% of the gold span length.

Aggregation across notes must be micro-averaged (sum TPs/counts, then
compute P/R/F1) so metrics are entity-level, not note-level.
"""


def spans_match_exact(pred: dict, gold: dict) -> bool:
    """Same field, identical boundaries."""
    return (
        pred["field"] == gold["field"]
        and pred["start"] == gold["start"]
        and pred["end"] == gold["end"]
    )


def spans_match_relaxed(pred: dict, gold: dict, tolerance: float = 0.10) -> bool:
    """Same field, each boundary within tolerance * gold span length."""
    if pred["field"] != gold["field"] or pred["start"] == -1:
        return False
    max_dev = max(1, round(tolerance * (gold["end"] - gold["start"])))
    return (
        abs(pred["start"] - gold["start"]) <= max_dev
        and abs(pred["end"] - gold["end"]) <= max_dev
    )


def match_spans(pred_spans: list[dict], gold_spans: list[dict], match_fn) -> int:
    """Greedy one-to-one matching; returns number of true positives."""
    matched_gold = set()
    tp = 0
    for pred in pred_spans:
        for i, gold in enumerate(gold_spans):
            if i in matched_gold:
                continue
            if match_fn(pred, gold):
                matched_gold.add(i)
                tp += 1
                break
    return tp


def prf(tp: int, n_pred: int, n_gold: int) -> dict:
    """Precision / recall / F1 from raw counts."""
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_gold if n_gold else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) else 0.0
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def evaluate_note(pred_spans: list[dict], gold_spans: list[dict]) -> dict:
    """All metrics for one note under both matching regimes."""
    tp_exact = match_spans(pred_spans, gold_spans, spans_match_exact)
    tp_relaxed = match_spans(pred_spans, gold_spans, spans_match_relaxed)

    n_pred, n_gold = len(pred_spans), len(gold_spans)
    non_verbatim = sum(1 for s in pred_spans if s["start"] == -1)

    return {
        "n_pred": n_pred,
        "n_gold": n_gold,
        "exact": {**prf(tp_exact, n_pred, n_gold), "tp": tp_exact},
        "relaxed": {**prf(tp_relaxed, n_pred, n_gold), "tp": tp_relaxed},
        "non_verbatim_rate": non_verbatim / n_pred if n_pred else 0.0,
    }