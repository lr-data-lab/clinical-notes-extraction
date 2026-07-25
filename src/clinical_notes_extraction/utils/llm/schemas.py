"""Pydantic models mirroring prompts/expected_template.md.

Manually kept in sync with the template: any schema change must be applied
in both places (template = what the model reads, Pydantic = what code checks).

extra="forbid": keys the model invents are a validation failure, not silently
dropped -- schema adherence is a reported metric, so it must be observable.
"""

from pydantic import BaseModel, ConfigDict


class MedicationAttributes(BaseModel):
    """Attribute spans for one medication. All values are literal spans (or null)."""

    model_config = ConfigDict(extra="forbid")

    active_substance: str | None
    commercial_name: str | None
    dosage_form: str | None
    dose: str | None
    dose_unit: str | None
    quantity: str | None
    route: str | None
    frequency: str | None
    duration: str | None
    indication: list[str]
    administration_instructions: str | None
    notes: str | None


class Medication(BaseModel):
    """One medication entry: the full line span plus its attribute spans."""

    model_config = ConfigDict(extra="forbid")

    span_text: str | None
    attributes: MedicationAttributes


class ExtractionOutput(BaseModel):
    """What the MODEL returns.

    note_id is echoed back from the prompt (nullable here so a model that omits
    it fails on value comparison, not on type validation).
    """

    model_config = ConfigDict(extra="forbid")

    medication_on_admission_text: str | None
    flag_is_medication_completed: bool | None
    medications: list[Medication]


class GroundTruthNote(BaseModel):
    """Ground truth file structure: note_id + the same nested payload."""

    model_config = ConfigDict(extra="forbid")

    note_id: str
    medication_on_admission_text: str | None
    flag_is_medication_completed: bool | None
    medications: list[Medication]