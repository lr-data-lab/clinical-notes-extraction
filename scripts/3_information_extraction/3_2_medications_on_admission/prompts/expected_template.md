# Expected Output Template

Your response must be a single valid JSON object following exactly this structure. Return only the JSON object, with no additional text, explanations, or markdown code fences.

```json
{
    "note_id": "string | not null",
    "medication_on_admission_text": "string | null",
    "medication_completeness": "boolean | Default: null",
    "medications": [
        {
            "span_text": "string | null",
            "attributes": {
                "Active Substance": "string | null",
                "Commercial Name": "string | null",
                "Dosage Form": "string | null",
                "Dose": "string | null",
                "Posology": "string | null",
                "Duration": "string | null",
                "Prescribing Physician": "string | null"
            }
        }
    ]
}
```

## Field definitions

- **note_id**: The unique identifier of the clinical note, copied exactly as provided in the input. Never null.
- **medication_on_admission_text**: The full text of the "Medications on Admission" section, copied verbatim from the note (no corrections, no reformatting). Null if the section is absent.
- **medication_completeness**: Whether the medication list appears complete. Set to false if the note explicitly indicates the list is incomplete or unreliable (e.g., "unable to verify", "Preadmissions medications listed are incomplete"). Set to true if the note explicitly indicates the list is complete (e.g., "The Preadmission Medication list is accurate and complete."). Null if there is no such indication or it cannot be determined.
- **medications**: A list with one object per distinct medication mention found in the "Medications on Admission" section. Empty list if the section states no medications (e.g., "None").
- **span_text**: The exact medication mention as it appears in the note, copied verbatim character by character (no expansion of abbreviations, no spelling or capitalization changes). Null only if no span can be identified.
- **Active Substance**: The generic or chemical name of the drug (e.g., "metoprolol", "atorvastatin"), exactly as written in the note. Null if only a commercial name is mentioned.
- **Commercial Name**: The brand or trade name of the drug (e.g., "Lopressor", "Lipitor"), exactly as written in the note. Null if only the generic name is mentioned.
- **Dosage Form**: The physical form of the medication (e.g., "tablet", "capsule", "cream", "solution"), exactly as written in the note. Null if not stated.
- **Dose**: The strength or amount administered at one time (e.g., "25 mg", "500 mg", "2 puffs"), exactly as written in the note, without frequency information. Null if not stated.
- **Posology**: The frequency and schedule of administration (e.g., "twice daily", "BID", "PRN", "at bedtime"), exactly as written in the note, without the dose amount. Null if not stated.
- **Duration**: The length of the treatment period (e.g., "for 7 days", "x 2 weeks"), exactly as written in the note. Null if not stated.
- **Prescribing Physician**: The name of the physician who prescribed the medication, exactly as written in the note. Null if not stated.