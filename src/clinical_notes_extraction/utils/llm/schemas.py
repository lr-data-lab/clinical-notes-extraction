"""Pydantic models mirroring prompts/expected_template.md.

Manually kept in sync with the template: any schema change must be applied
in both places (template = what the model reads, Pydantic = what code checks).
"""

from pydantic import BaseModel


class MedicationAttributes(BaseModel):
    """Attribute spans for one medication. All values are literal spans (or null)."""

    active_substance: str | None
    commercial_name: str | None
    dosage_form: str | None
    dose: str | None
    dose_unit: str | None
    quantity: str | None
    route: str | None
    frequency: str | None
    duration: str | None
    indication: list[str] | None
    administration_instructions: str | None
    notes: str | None


class Medication(BaseModel):
    """One medication entry: the full line span plus its attribute spans."""

    span_text: str | None
    attributes: MedicationAttributes


class ExtractionOutput(BaseModel):
    """What the MODEL returns. note_id and section text are caller-side metadata."""

    flag_is_medication_completed: bool | None
    medications: list[Medication]


class GroundTruthNote(BaseModel):
    """Ground truth file structure: note_id + the same nested payload."""

    note_id: str
    medication_on_admission_text: str | None
    flag_is_medication_completed: bool | None
    medications: list[Medication]