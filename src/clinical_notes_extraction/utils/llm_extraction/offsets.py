"""Programmatic character offsets and verbatim verification.

Offsets are NEVER produced by the model or entered manually: they are
computed here with note_text.find(). start == -1 flags non-verbatim
output (paraphrase/hallucination) and, on ground truth, copy-paste errors.

The medication-level span_text anchors a search window so attribute
spans are located inside their own medication line, fixing the
first-occurrence ambiguity of a global find() for repeated strings
(e.g. "daily", "PO").
"""

ATTRIBUTE_FIELDS = [
    "active_substance", "commercial_name", "dosage_form", "dose",
    "dose_unit", "quantity", "route", "frequency", "duration",
    "indication", "administration_instructions", "notes",
]


def _find_span(
    value: str,
    note_text: str,
    window: tuple[int, int] | None,
) -> tuple[int, int]:
    """Locate a literal span; search inside the medication window first.

    Returns (start, end); (-1, -1) means non-verbatim output.
    """
    if window is not None and window[0] != -1:
        local = note_text.find(value, window[0], window[1])
        if local != -1:
            return local, local + len(value)
    # Fallback: whole-note search (window missing or attribute outside it)
    start = note_text.find(value)
    return (start, start + len(value)) if start != -1 else (-1, -1)


def compute_spans(medications: list[dict], note_text: str) -> list[dict]:
    """Convert model/ground-truth medications into flat span records.

    - Emits one record per non-null field value.
    - indication is array<string>: each element becomes its own record.
    - Output record: {med_idx, field, span_text, start, end}.
    """
    spans = []
    for med_idx, med in enumerate(medications):
        window = None

        # Medication-level span (anchors the attribute search window)
        med_span = med.get("span_text")
        if med_span is not None:
            start = note_text.find(med_span)
            end = start + len(med_span) if start != -1 else -1
            spans.append({
                "med_idx": med_idx, "field": "span_text",
                "span_text": med_span, "start": start, "end": end,
            })
            if start != -1:
                window = (start, end)

        # Attribute-level spans, searched within the medication window
        attributes = med.get("attributes", {})
        for field in ATTRIBUTE_FIELDS:
            value = attributes.get(field)
            if value is None:
                continue
            values = value if isinstance(value, list) else [value]
            for item in values:
                start, end = _find_span(item, note_text, window)
                spans.append({
                    "med_idx": med_idx, "field": field,
                    "span_text": item, "start": start, "end": end,
                })
    return spans