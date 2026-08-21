# Task

Extract all medications listed in the **"Medications on Admission"** section of the clinical note below.

The note is a full discharge summary — locate the admission medication section yourself and ignore every other section, including "Discharge Medications".


## Demonstrations

The demonstration material below shows the expected output format. Follow its structure, not its content.

{EXAMPLES}

**The demonstration material above illustrates structure ONLY, never content:**

- **Source Material:** Every extracted medication and attribute value in your response MUST come exclusively from the clinical note at the end of this prompt.
- **Dynamic Extraction:** `medications_text` MUST contain the verbatim text of the admission medication section of that same clinical note. **NEVER** copy `medications_text`, medication names, or attribute values from the demonstration material above.


## Expected output template

Return a single valid JSON object strictly matching the template and structure shown below. Output ONLY that JSON object, without any introductory text, markdown commentary, or post-extraction explanations.

Every medication found in the section becomes one entry in the `medications` array of that single top-level object. Never emit more than one top-level JSON object, and never move attribute fields out of the nested `attributes` object.

{EXPECTED_TEMPLATE}


## Rules

- Do not invent values. Only fill a field if the information is written in the note.
- **Never infer, complete or normalise a value.** With the single exception of `flag_is_medication_completed`, every field must be copied from text that is explicitly present in the note. If the information is not written there, the field is unstated — even when the correct value is obvious from medical knowledge. In particular:
  - Do not derive an active substance from a brand name, or a brand name from a substance.
  - Do not expand abbreviations, correct spelling, or normalise casing.
  - Do not infer `route` from the dosage form, or `dosage_form` from the route.
  - Do not infer `indication` from what the drug is typically prescribed for; it is
    filled only when the note states the reason for that specific medication.
  - Do not supply a customary `dose`, `quantity`, `frequency` or `duration` because it is the standard regimen for that drug.
  - Do not resolve ambiguous or redacted text (`___`, unexplained marks) into a guessed value.
- If the note contains no admission medication section at all, set `medications_text` to `null`, `flag_is_medication_completed` to `null`, and `medications` to the empty array `[]`. Never emit a medication object to stand for an absent medication: every object in `medications` requires a non-null `span_text` copied from the note.
- Keep every extracted string exactly as it appears in the source (same casing, punctuation and spacing).


## Clinical note to be extracted

Clinical note to be used to extract every medication the patient was taking on admission:

{NOTE_TEXT}