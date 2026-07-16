# Expected Output Template

Your response must be a single valid JSON object following exactly this structure. Return only the JSON object, with no additional text, explanations, or markdown code fences.

```json
{
    "note_id": "string | not null",
    "medication_on_admission_text": "string | null",
    "flag_is_medication_completed": "boolean | Default: null",
    "medications": [
        {
            "span_text": "string | null",
            "attributes": {
                "active_substance": "string | null",
                "commercial_name": "string | null",
                "dosage_form": "string | null",
                "dose": "string | null",
                "route": "string | null",
                "frequency": "string | null",
                "duration": "string | null",
                "indication": "array<string> | null",
                "administration_instructions": "string | null",
                "prescribing_physician": "string | null"
            }
        }
    ]
}
```

## Field definitions

- **note_id**: The unique identifier of the clinical note, copied exactly as provided in the input. Never null.
- **medication_on_admission_text**: The full text of the "Medications on Admission" section, copied verbatim from the note (no corrections, no reformatting). Null if the section is absent.
- **flag_is_medication_completed**: Whether the medication list appears complete. Set to false if the note explicitly indicates the list is incomplete or unreliable (e.g., "unable to verify", "Preadmissions medications listed are incomplete"). Set to true if the note explicitly indicates the list is complete (e.g., "The Preadmission Medication list is accurate and complete."). Null if there is no such indication or it cannot be determined.
- **medications**: A list with one object per distinct medication mention found in the "Medications on Admission" section. Empty list if the section states no medications (e.g., "None").
- **span_text**: The exact medication mention as it appears in the note, copied verbatim character by character (no expansion of abbreviations, no spelling or capitalization changes). Null only if no span can be identified.
- **active_substance**: The generic or chemical name of the drug (e.g., "metoprolol", "atorvastatin"), exactly as written in the note. Null if only a commercial name is mentioned.
- **commercial_name**: The brand or trade name of the drug (e.g., "Lopressor", "Lipitor"), exactly as written in the note. Null if only the generic name is mentioned.
- **dosage_form**: The physical form of the medication (e.g., "tablet", "capsule", "cream", "solution"), exactly as written in the note. Null if not stated.
- **dose**: The amount of drug expressed in mass, volume, or concentration units — mg, g, mcg, mEq, mL, %, mg/mL. Annotate exactly as written, preserving the source spacing (110mcg, not 110 mcg). Its meaning depends on quantity: when quantity is null, dose is the amount administered at one time (Amiodarone 100 mg PO DAILY → 100 mg); when quantity is populated, dose is the strength contained in each unit, and the amount administered is the product of the two (Fluticasone Propionate 110mcg 2 PUFF → 110mcg per puff, 220 mcg administered). Never include count units, route, or frequency. Null if no mass, volume, or concentration is stated (Albuterol Inhaler 2 PUFF IH Q6H:PRN sob → null).
- **quantity**: The number of discrete units administered at one time, expressed in count units — PUFF, DROP, TAB, CAP, SPRAY, PATCH, SUPP. Annotate the number together with its unit, exactly as written (2 PUFF, 1 DROP, 1 TAB), preserving the source's capitalisation. Do not infer a count when none is stated: a line giving only a mass (Amiodarone 100 mg) has quantity null, even though it is implicitly one tablet. Never include frequency information.
- **route**: The route of administration — the path by which the drug enters the body. Annotate the abbreviation exactly as it appears in the source text. Do not confuse with dosage_form, which describes the physical presentation of the drug (tablet, capsule, solution, patch). A single line may carry both (Ondansetron 4 mg IV ODT → route IV, dosage form ODT). Null when no route is stated.
- **frequency**: The frequency and schedule of administration (e.g., "PO Daily", "BID", "PRN", "at bedtime"), exactly as written in the note, without the dose amount. Null if not stated.
- **duration**: The length of the treatment period (e.g., "for 7 days", "x 2 weeks"), exactly as written in the note. Null if not stated.
- **indication**: The clinical reason or triggering condition for administering the drug — the "why". Most commonly found after a PRN marker, following the colon separator where present (Q6H:PRN pain → pain). Annotate the span literally, preserving severity qualifiers as written (Pain - Mild, not pain); normalisation is a downstream task. Do not include the PRN marker itself, which belongs to frequency. Null when no indication is stated.
- **administration_instructions**: Free-text directions governing how or under what conditions the drug is given, which do not fit any other attribute. Includes hold parameters (hold for sbp<100, hold if HR<60), intake conditions (take with food, on an empty stomach, do not crush), titration or adjustment rules (titrate to effect, per sliding scale), and application sites (to affected area, both eyes). Distinct from indication: an indication triggers administration, an instruction constrains it. Null when no such text is present.
- **prescribing_physician**: The name of the physician who prescribed the medication, exactly as written in the note. Null if not stated.