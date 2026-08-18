"""Pydantic models mirroring prompts/expected_template.md.

Manually kept in sync with the template: any schema change must be applied
in both places (template = what the model reads, Pydantic = what code checks).

extra="forbid": keys the model invents are a validation failure, not silently
dropped -- schema adherence is a reported metric, so it must be observable.

strict=True: no type coercion. The template requires the JSON literals
true/false/null for flag_is_medication_completed and strings everywhere else;
in lax mode Pydantic would accept "true" or 100 and convert them, hiding a
schema violation that is supposed to be counted.

Scope: this module checks STRUCTURE only. Whether a span actually occurs in
the source note is extraction quality, not schema conformance, and is measured
separately -- otherwise a model that emits a perfect envelope with invented
content becomes indistinguishable from one that cannot produce the format.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# The template forbids "" and "N/A" placeholders: an absent value is null.
# Empty or whitespace-only strings are therefore a violation, not a value.
# span_text and attribute strings must be non-empty spans.
Span = Annotated[str, StringConstraints(min_length=1, strip_whitespace=False)]


class MedicationAttributes(BaseModel):
    """Attribute spans for one medication. All values are literal spans (or null/empty list)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    active_substance: Span | None
    commercial_name: Span | None
    dosage_form: Span | None
    dose: list[Span]  # Array of strings ([] when empty, never null)
    quantity: Span | None
    route: Span | None
    frequency: list[Span]  # Array of strings ([] when empty, never null)
    duration: Span | None
    indication: list[Span]  # Array of strings ([] when empty, never null)
    administration_instructions: Span | None


class Medication(BaseModel):
    """One medication entry: the full line span plus its attribute spans.

    span_text is never null: it anchors every attribute to a character offset
    in the source, so a medication without one cannot exist.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    span_text: Span
    attributes: MedicationAttributes


class ExtractionOutput(BaseModel):
    """What the MODEL returns: the three top-level keys of the template."""

    model_config = ConfigDict(extra="forbid", strict=True)

    medications_text: str | None  # String or null; permitted to contain multi-line text (\n)
    flag_is_medication_completed: bool | None  # JSON literal true, false, or null
    medications: list[Medication]  # List of extracted medication objects ([] when empty)


class NoteId(BaseModel):
    """note_id carrier, kept separate so it can be ordered before the payload."""

    model_config = ConfigDict(extra="forbid", strict=True)

    note_id: Span


class GroundTruthNote(ExtractionOutput, NoteId):
    """Ground truth file structure: note_id plus the same payload.

    Inherits the payload from ExtractionOutput so the two can never drift: a
    schema change lands in one place. note_id is the annotation's own key and
    is not part of what the model produces.

    Base order is deliberate and counter-intuitive. Pydantic collects fields in
    REVERSE MRO order, so the last base listed contributes its fields first --
    (ExtractionOutput, NoteId) yields note_id, medications_text, ... while
    (NoteId, ExtractionOutput) would put note_id last. Do not swap them.
    """