"""Exact-match evaluation for the medication extraction pipeline.

One *slot* = one key of the annotation JSON:

* the top-level keys in :data:`TOP_LEVEL_KEYS`;
* every attribute of every medication (:data:`ATTRIBUTES`).

Medications are compared position by position (medication 1 vs medication 1,
medication 2 vs medication 2). A slot counts as:

======  =====================================================================
TP      gold has a value and the prediction is exactly equal to it
FP      the prediction has a value that is not the gold one (gold may be null)
FN      gold has a value and the prediction does not reproduce it exactly
======  =====================================================================

Both null is a true negative and is not counted (otherwise every run scores
~0.95 just for leaving rarely-filled keys empty).

Precision, recall and F1 are micro-averaged over all slots of all notes, per
model and per prompting strategy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from itertools import zip_longest
from pathlib import Path
from typing import Any, Iterable, Mapping

__all__ = [
    "ATTRIBUTES",
    "TOP_LEVEL_KEYS",
    "Counts",
    "normalise",
    "evaluate_note",
    "evaluate_run",
    "evaluate_all",
    "load_ground_truth",
    "load_ground_truth_dir",
    "load_results",
    "load_results_tree",
    "metrics_table",
    "metrics_to_latex",
    "metrics_to_html",
    "metrics_to_docx",
]

# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #

ATTRIBUTES: tuple[str, ...] = (
    "active_substance",
    "commercial_name",
    "dosage_form",
    "dose",
    "dose_unit",
    "quantity",
    "route",
    "frequency",
    "duration",
    "indication",
    "administration_instructions",
    "notes",
)

#: attributes annotated as a list of strings (compared as a set, order-insensitive)
LIST_ATTRIBUTES: frozenset[str] = frozenset({"indication"})

#: top-level keys that are scored.
#: ``medications_text`` is excluded by default: it is the copied source text,
#: not an extraction decision. Add it here if you want it scored.
TOP_LEVEL_KEYS: tuple[str, ...] = ("flag_is_medication_completed",)

#: keys of one result record
NOTE_ID_KEY, MODEL_KEY, STRATEGY_KEY = "note_id", "model", "strategy"
OUTPUT_KEY, STATUS_KEY, OK_STATUS = "output", "status", "ok"


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #


def normalise(value: Any, *, casefold: bool = False) -> Any:
    """Canonicalise a value so that it can be compared; ``None`` means absent.

    Only surrounding whitespace is forgiven. Set ``casefold=True`` to also
    ignore capitalisation.
    """
    if isinstance(value, (list, tuple, set)):
        items = [normalise(v, casefold=casefold) for v in value]
        items = [v for v in items if v is not None]
        return tuple(sorted(items, key=str)) if items else None
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    text = " ".join(str(value).split())
    if not text:
        return None
    return text.casefold() if casefold else text


@dataclass
class Counts:
    """True positives / false positives / false negatives over slots."""

    tp: int = 0
    fp: int = 0
    fn: int = 0

    def __add__(self, other: "Counts") -> "Counts":
        return Counts(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)

    __radd__ = __add__

    @property
    def precision(self) -> float:
        predicted = self.tp + self.fp
        return self.tp / predicted if predicted else 0.0

    @property
    def recall(self) -> float:
        support = self.tp + self.fn
        return self.tp / support if support else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "support": self.tp + self.fn,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


def _compare_slot(gold: Any, pred: Any) -> Counts:
    """TP/FP/FN for a single key."""
    if gold is None and pred is None:
        return Counts()  # true negative, not counted
    if gold == pred:
        return Counts(tp=1)
    return Counts(fp=int(pred is not None), fn=int(gold is not None))


def _attributes(medication: Any) -> Mapping[str, Any]:
    if not isinstance(medication, Mapping):
        return {}
    attrs = medication.get("attributes")
    return attrs if isinstance(attrs, Mapping) else {}


def _medications(note: Any) -> list[Any]:
    if not isinstance(note, Mapping):
        return []
    meds = note.get("medications")
    return meds if isinstance(meds, list) else []


@dataclass
class NoteCounts:
    """Slot counts for one note, in total and broken down per key."""

    note_id: str = ""
    total: Counts = field(default_factory=Counts)
    per_key: dict[str, Counts] = field(default_factory=dict)
    n_gold_medications: int = 0
    n_pred_medications: int = 0
    valid: bool = True

    def add(self, key: str, counts: Counts) -> None:
        self.per_key[key] = self.per_key.get(key, Counts()) + counts
        self.total = self.total + counts


def evaluate_note(
    gold: Mapping[str, Any],
    pred: Any,
    *,
    note_id: str = "",
    casefold: bool = False,
    top_level_keys: Iterable[str] = TOP_LEVEL_KEYS,
) -> NoteCounts:
    """Compare one predicted note with its annotation, key by key.

    ``pred`` may be ``None`` (missing or invalid output): every annotated slot
    then counts as a false negative.
    """
    valid = isinstance(pred, Mapping)
    pred_note: Mapping[str, Any] = pred if valid else {}

    result = NoteCounts(
        note_id=note_id or str(gold.get(NOTE_ID_KEY, "")),
        n_gold_medications=len(_medications(gold)),
        n_pred_medications=len(_medications(pred_note)),
        valid=valid,
    )

    for key in top_level_keys:
        result.add(
            key,
            _compare_slot(
                normalise(gold.get(key), casefold=casefold),
                normalise(pred_note.get(key), casefold=casefold),
            ),
        )

    for gold_med, pred_med in zip_longest(
        _medications(gold), _medications(pred_note), fillvalue=None
    ):
        gold_attrs, pred_attrs = _attributes(gold_med), _attributes(pred_med)
        for name in ATTRIBUTES:
            result.add(
                name,
                _compare_slot(
                    normalise(gold_attrs.get(name), casefold=casefold),
                    normalise(pred_attrs.get(name), casefold=casefold),
                ),
            )

    return result


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #


@dataclass
class RunCounts:
    """Aggregated counts for one (model, strategy) pair."""

    model: str = ""
    strategy: str = ""
    notes: list[NoteCounts] = field(default_factory=list)

    @property
    def total(self) -> Counts:
        return sum((n.total for n in self.notes), Counts())

    @property
    def per_key(self) -> dict[str, Counts]:
        out: dict[str, Counts] = {}
        for note in self.notes:
            for key, counts in note.per_key.items():
                out[key] = out.get(key, Counts()) + counts
        return out

    @property
    def n_notes(self) -> int:
        return len(self.notes)

    @property
    def invalid_rate(self) -> float:
        return sum(not n.valid for n in self.notes) / self.n_notes if self.notes else 0.0

    def record(self) -> dict[str, Any]:
        """One flat row per run."""
        return {
            "model": self.model,
            "strategy": self.strategy,
            "n_notes": self.n_notes,
            "invalid_rate": self.invalid_rate,
            **self.total.as_dict(),
        }

    def per_key_records(self) -> list[dict[str, Any]]:
        """One flat row per key."""
        counts = self.per_key
        keys = list(TOP_LEVEL_KEYS) + list(ATTRIBUTES)
        return [
            {
                "model": self.model,
                "strategy": self.strategy,
                "key": key,
                **counts.get(key, Counts()).as_dict(),
            }
            for key in keys
        ]

    def per_note_records(self) -> list[dict[str, Any]]:
        """One flat row per note.

        A note where nothing was counted (no annotated value and no predicted
        value, e.g. an empty medication list correctly predicted as empty) gets
        ``nan`` instead of 0.0, so that it does not sink to the bottom of a
        "hardest notes" ranking.
        """
        rows = []
        for note in self.notes:
            metrics = note.total.as_dict()
            if note.total.tp + note.total.fp + note.total.fn == 0:
                metrics.update(precision=float("nan"), recall=float("nan"), f1=float("nan"))
            rows.append(
                {
                    "model": self.model,
                    "strategy": self.strategy,
                    "note_id": note.note_id,
                    "valid": note.valid,
                    "n_gold_medications": note.n_gold_medications,
                    "n_pred_medications": note.n_pred_medications,
                    **metrics,
                }
            )
        return rows


def evaluate_run(
    gold_by_id: Mapping[str, Mapping[str, Any]],
    pred_by_id: Mapping[str, Any],
    *,
    model: str = "",
    strategy: str = "",
    casefold: bool = False,
    skip_invalid: bool = False,
) -> RunCounts:
    """Evaluate one (model, strategy) over every annotated note.

    Notes that the run did not produce, and notes whose extraction failed, are
    scored as missing predictions: every annotated slot becomes a false
    negative. A run therefore cannot gain by skipping the hard notes.

    ``skip_invalid=True`` drops those notes instead. That answers a different
    question -- "how good is the output *when* the model produces valid JSON" --
    and must always be read together with ``invalid_rate``.
    """
    run = RunCounts(model=model, strategy=strategy)
    for note_id, gold in gold_by_id.items():
        pred = pred_by_id.get(note_id)
        if skip_invalid and not isinstance(pred, Mapping):
            continue
        run.notes.append(
            evaluate_note(gold, pred, note_id=note_id, casefold=casefold)
        )
    return run


def evaluate_all(
    gold_by_id: Mapping[str, Mapping[str, Any]],
    records: Iterable[Mapping[str, Any]],
    *,
    casefold: bool = False,
    skip_invalid: bool = False,
) -> dict[tuple[str, str], RunCounts]:
    """Evaluate a flat list of result records, grouped by (model, strategy)."""
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (str(record.get(MODEL_KEY, "")), str(record.get(STRATEGY_KEY, "")))
        note_id = str(record.get(NOTE_ID_KEY, ""))
        output = record.get(OUTPUT_KEY)
        if record.get(STATUS_KEY, OK_STATUS) != OK_STATUS:
            output = None
        grouped.setdefault(key, {})[note_id] = output

    return {
        (model, strategy): evaluate_run(
            gold_by_id,
            preds,
            model=model,
            strategy=strategy,
            casefold=casefold,
            skip_invalid=skip_invalid,
        )
        for (model, strategy), preds in grouped.items()
    }


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def _read_json(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        if str(path).endswith(".jsonl"):
            return [json.loads(line) for line in handle if line.strip()]
        return json.load(handle)


def load_ground_truth(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load annotations from ``{note_id: note}``, ``[note, ...]`` or JSONL."""
    data = _read_json(path)
    if isinstance(data, Mapping) and NOTE_ID_KEY not in data:
        return {str(k): v for k, v in data.items()}
    if isinstance(data, Mapping):
        data = [data]
    return {str(note[NOTE_ID_KEY]): note for note in data if NOTE_ID_KEY in note}


def load_results(*paths: str | Path) -> list[dict[str, Any]]:
    """Load result records from one or more JSON / JSONL files."""
    records: list[dict[str, Any]] = []
    for path in paths:
        data = _read_json(path)
        records.extend(data if isinstance(data, list) else [data])
    return records


def load_ground_truth_dir(directory: str | Path, pattern: str = "*.json") -> dict[str, dict[str, Any]]:
    """Load one annotation per file, e.g. ``ground_truth/development/10176936-DS-19.json``.

    The note id is taken from the ``note_id`` key when present, otherwise from
    the file name.
    """
    notes: dict[str, dict[str, Any]] = {}
    for path in sorted(Path(directory).glob(pattern)):
        note = _read_json(path)
        if not isinstance(note, Mapping):
            continue
        notes[str(note.get(NOTE_ID_KEY) or path.stem)] = dict(note)
    return notes


def _records_from_dir(
    directory: Path, model: str, strategy: str | None, *, failed: bool
) -> list[dict[str, Any]]:
    records = []
    for path in sorted(directory.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping) and OUTPUT_KEY in payload:
            record = dict(payload)
        else:
            record = {OUTPUT_KEY: payload}
        record.setdefault(NOTE_ID_KEY, path.stem)
        record[MODEL_KEY] = record.get(MODEL_KEY) or model
        record[STRATEGY_KEY] = record.get(STRATEGY_KEY) or strategy or "unknown"
        record[STATUS_KEY] = "error" if failed else record.get(STATUS_KEY, OK_STATUS)
        record["path"] = str(path)
        records.append(record)
    return records


def load_results_tree(
    run_dir: str | Path,
    *,
    ignored_dirs: Iterable[str] = ("prompts",),
    errors_dirname: str = "errors",
) -> list[dict[str, Any]]:
    """Load a run directory laid out as ``<run>/<model>/<strategy>/<note_id>.json``.

    Failed extractions are expected under ``<run>/<model>/errors/<strategy>/``;
    they are loaded too and marked ``status="error"`` so that they can be
    scored as missing output instead of silently disappearing from the
    denominator.
    """
    run_dir = Path(run_dir)
    ignored = set(ignored_dirs)
    records: list[dict[str, Any]] = []

    for model_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        model = model_dir.name
        for child in sorted(p for p in model_dir.iterdir() if p.is_dir()):
            if child.name in ignored:
                continue
            if child.name == errors_dirname:
                # errors/<strategy>/*.json, plus any loose file directly in errors/
                for strategy_dir in sorted(p for p in child.iterdir() if p.is_dir()):
                    records += _records_from_dir(
                        strategy_dir, model, strategy_dir.name, failed=True
                    )
                records += _records_from_dir(child, model, None, failed=True)
            else:
                records += _records_from_dir(child, model, child.name, failed=False)

    return records


# --------------------------------------------------------------------------- #
# Publication table (keys x models/strategies, with P/R/F1 sub-columns)
# --------------------------------------------------------------------------- #


def _pretty(name: str) -> str:
    """LaTeX-safe label: no underscores."""
    return str(name).replace("_", " ")


def metrics_table(
    results: Mapping[tuple[str, str], "RunCounts"],
    *,
    keys: Iterable[str] | None = None,
    models: Iterable[str] | None = None,
    strategies: Iterable[str] | None = None,
    drop_empty: bool = True,
    drop_constant_levels: bool = True,
    macro: bool = True,
    micro: bool = True,
):
    """Build the final table: one row per key, P/R/F1 per (model, strategy).

    ``models`` / ``strategies`` restrict the columns, so the same function
    produces the full grid, one table per model, or one table per strategy.

    ``drop_constant_levels`` removes the column level that has a single value,
    so a one-model table is headed by the strategies alone (and vice versa).

    ``Macro`` is the unweighted mean of the rows shown (every key counts the
    same, as in the reference table); ``Micro`` pools the counts of all those
    keys and therefore equals the run-level number.
    """
    import pandas as pd

    selected = sorted(
        (
            (model, strategy, run)
            for (model, strategy), run in results.items()
            if (models is None or model in set(models))
            and (strategies is None or strategy in set(strategies))
        ),
        key=lambda item: (item[0], item[1]),
    )
    if not selected:
        raise ValueError("no run matches the requested models/strategies")

    counts_by_run = {(m, s): run.per_key for m, s, run in selected}

    row_keys = list(keys) if keys is not None else list(TOP_LEVEL_KEYS) + list(ATTRIBUTES)
    if drop_empty:
        row_keys = [
            key
            for key in row_keys
            if any(
                per_key.get(key, Counts()).tp
                + per_key.get(key, Counts()).fp
                + per_key.get(key, Counts()).fn
                for per_key in counts_by_run.values()
            )
        ]

    records = []
    for (model, strategy), per_key in counts_by_run.items():
        selected_counts = [per_key.get(key, Counts()) for key in row_keys]

        for key, counts in zip(row_keys, selected_counts):
            records.append(
                {
                    "row": _pretty(key),
                    "model": model,
                    "strategy": strategy,
                    "P": counts.precision,
                    "R": counts.recall,
                    "F1": counts.f1,
                }
            )

        if macro and selected_counts:
            records.append(
                {
                    "row": "Macro",
                    "model": model,
                    "strategy": strategy,
                    "P": sum(c.precision for c in selected_counts) / len(selected_counts),
                    "R": sum(c.recall for c in selected_counts) / len(selected_counts),
                    "F1": sum(c.f1 for c in selected_counts) / len(selected_counts),
                }
            )
        if micro:
            pooled = sum(selected_counts, Counts())
            records.append(
                {
                    "row": "Micro",
                    "model": model,
                    "strategy": strategy,
                    "P": pooled.precision,
                    "R": pooled.recall,
                    "F1": pooled.f1,
                }
            )

    order = [_pretty(key) for key in row_keys] + (["Macro"] if macro else []) + (["Micro"] if micro else [])

    table = (
        pd.DataFrame(records)
        .set_index(["row", "model", "strategy"])
        .unstack(["model", "strategy"])
        .reorder_levels(["model", "strategy", None], axis=1)
        .sort_index(axis=1, level=[0, 1])
        .reindex(order)
    )
    # keep P, R, F1 in that order inside each (model, strategy) block
    table = table.reindex(
        columns=pd.MultiIndex.from_tuples(
            [
                (model, strategy, metric)
                for model, strategy in dict.fromkeys(
                    (m, s) for m, s, _ in selected
                )
                for metric in ("P", "R", "F1")
            ]
        )
    )
    if drop_constant_levels:
        n_models = len({col[0] for col in table.columns})
        n_strategies = len({col[1] for col in table.columns})
        if n_models == 1 and n_strategies > 1:
            table.columns = table.columns.droplevel(0)
        elif n_strategies == 1 and n_models > 1:
            table.columns = table.columns.droplevel(1)

    table.index.name = "Key"
    return table


def metrics_to_latex(
    table,
    *,
    caption: str = "Exact-match Precision, Recall and F1 per key.",
    label: str = "tab:exact-match",
    decimals: int = 2,
    bold_best_f1: bool = True,
) -> str:
    """Render :func:`metrics_table` as LaTeX, bolding the best F1 of each row."""
    import pandas as pd

    formatted = table.map(lambda v: "--" if pd.isna(v) else f"{v:.{decimals}f}")

    if bold_best_f1:
        f1_columns = [col for col in table.columns if col[-1] == "F1"]
        if len(f1_columns) > 1:
            for row in table.index:
                values = table.loc[row, f1_columns]
                if values.notna().any() and values.max() > 0:
                    for col in f1_columns:
                        if table.loc[row, col] == values.max():
                            formatted.loc[row, col] = f"\\textbf{{{formatted.loc[row, col]}}}"

    formatted.columns = pd.MultiIndex.from_tuples(
        [tuple(_pretty(level) for level in col) for col in table.columns]
    )
    return formatted.to_latex(
        caption=caption,
        label=label,
        escape=False,
        multicolumn=True,
        multicolumn_format="c",
        column_format="l" + "r" * len(formatted.columns),
    )


# --------------------------------------------------------------------------- #
# Word / HTML export
# --------------------------------------------------------------------------- #


def _formatted_cells(table, decimals: int, bold_best_f1: bool):
    """Return (list of body rows as strings, set of (row, col) to bold)."""
    import pandas as pd

    def fmt(value: Any) -> str:
        if isinstance(value, float):
            return "--" if pd.isna(value) else f"{value:.{decimals}f}"
        return "" if value is None else str(value)

    text = [[fmt(value) for value in row] for row in table.to_numpy()]

    bold: set[tuple[int, int]] = set()
    if bold_best_f1:
        f1_positions = [
            i
            for i, col in enumerate(table.columns)
            if (col[-1] if isinstance(col, tuple) else col) in ("F1", "f1")
        ]
        if len(f1_positions) > 1:
            values = table.iloc[:, f1_positions]
            for r in range(len(table.index)):
                row_values = values.iloc[r]
                if row_values.notna().any() and row_values.max() > 0:
                    for offset, col_index in enumerate(f1_positions):
                        if row_values.iloc[offset] == row_values.max():
                            bold.add((r, col_index))
    return text, bold


def _header_runs(columns, level: int) -> list[tuple[str, int]]:
    """Consecutive spans of identical labels at one level of a column index."""
    runs: list[list[Any]] = []
    previous = object()
    for col in columns:
        prefix = tuple(col[: level + 1]) if isinstance(col, tuple) else (col,)
        label = col[level] if isinstance(col, tuple) else col
        if prefix == previous:
            runs[-1][1] += 1
        else:
            runs.append([label, 1])
            previous = prefix
    return [(str(label), span) for label, span in runs]


def metrics_to_html(
    table,
    *,
    caption: str = "",
    decimals: int = 2,
    bold_best_f1: bool = True,
) -> str:
    """Render a table as a self-contained HTML page.

    Open it in a browser and copy-paste into Word: the merged header cells, the
    bold F1 values and the borders survive the paste. Useful when python-docx is
    not available.
    """
    text, bold = _formatted_cells(table, decimals, bold_best_f1)
    n_index = table.index.nlevels
    n_levels = table.columns.nlevels

    head = []
    for level in range(n_levels - 1):
        cells = "".join(
            f'<th colspan="{span}">{label}</th>' for label, span in _header_runs(table.columns, level)
        )
        head.append(f'<tr><th colspan="{n_index}"></th>{cells}</tr>')

    names = [name or "" for name in (table.index.names if n_index > 1 else [table.index.name])]
    last = "".join(f"<th>{name}</th>" for name in names)
    last += "".join(
        f"<th>{col[-1] if isinstance(col, tuple) else col}</th>" for col in table.columns
    )
    head.append(f"<tr>{last}</tr>")

    body = []
    for r, index_value in enumerate(table.index):
        labels = index_value if isinstance(index_value, tuple) else (index_value,)
        cells = "".join(f"<th>{label}</th>" for label in labels)
        for c, value in enumerate(text[r]):
            cells += f"<td><b>{value}</b></td>" if (r, c) in bold else f"<td>{value}</td>"
        body.append(f"<tr>{cells}</tr>")

    return (
        "<!doctype html><meta charset='utf-8'>"
        "<style>"
        "body{font-family:Calibri,Arial,sans-serif;font-size:11pt}"
        "table{border-collapse:collapse}"
        "th,td{border:1px solid #999;padding:3px 8px;text-align:center}"
        "th:first-child,tr>th:first-child{text-align:left}"
        "td{text-align:right}"
        "caption{caption-side:top;text-align:left;padding-bottom:6px}"
        "</style>"
        "<table>"
        + (f"<caption>{caption}</caption>" if caption else "")
        + "<thead>"
        + "".join(head)
        + "</thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def metrics_to_docx(
    tables: Mapping[str, Any],
    path: str | Path,
    *,
    decimals: int = 2,
    bold_best_f1: bool = True,
    landscape: bool = True,
    title: str = "",
) -> Path:
    """Write one or more tables to a .docx, ready to copy into the thesis.

    ``tables`` maps a caption to a DataFrame (insertion order is kept). The
    index is written as the leading column(s), so set a meaningful index before
    calling. Requires ``python-docx`` (``pip install python-docx``).
    """
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    document = Document()
    if landscape:
        section = document.sections[0]
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = section.page_height, section.page_width

    if title:
        document.add_heading(title, level=1)

    for caption, table in tables.items():
        text, bold = _formatted_cells(table, decimals, bold_best_f1)
        n_index = table.index.nlevels
        n_levels = table.columns.nlevels
        n_cols = n_index + len(table.columns)

        paragraph = document.add_paragraph(caption)
        paragraph.runs[0].bold = True

        word_table = document.add_table(rows=n_levels + len(table.index), cols=n_cols)
        word_table.style = "Table Grid"
        word_table.autofit = True

        # header: one row per column level, group labels merged
        for level in range(n_levels - 1):
            column = n_index
            for label, span in _header_runs(table.columns, level):
                cell = word_table.cell(level, column)
                if span > 1:
                    cell = cell.merge(word_table.cell(level, column + span - 1))
                cell.text = label
                column += span

        header = n_levels - 1
        names = list(table.index.names) if n_index > 1 else [table.index.name]
        for i, name in enumerate(names):
            word_table.cell(header, i).text = str(name or "")
        for j, col in enumerate(table.columns):
            word_table.cell(header, n_index + j).text = str(
                col[-1] if isinstance(col, tuple) else col
            )

        # body
        for r, index_value in enumerate(table.index):
            row = n_levels + r
            labels = index_value if isinstance(index_value, tuple) else (index_value,)
            for i, label in enumerate(labels):
                word_table.cell(row, i).text = str(label)
            for c, value in enumerate(text[r]):
                cell = word_table.cell(row, n_index + c)
                cell.text = value
                if (r, c) in bold:
                    cell.paragraphs[0].runs[0].bold = True

        # cosmetics: small font, centred numbers, bold header
        for r, row in enumerate(word_table.rows):
            for c, cell in enumerate(row.cells):
                for paragraph in cell.paragraphs:
                    if c >= n_index:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in paragraph.runs:
                        run.font.size = Pt(9)
                        if r < n_levels:
                            run.font.bold = True

        document.add_paragraph()

    path = Path(path)
    document.save(path)
    return path
