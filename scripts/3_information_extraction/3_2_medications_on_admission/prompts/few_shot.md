# Task

Extract all medications listed in the **"Medications on Admission"** section of the clinical note below.

The note is a full discharge summary — locate the admission medication section yourself and ignore every other section, including "Discharge Medications".


## Examples

The following examples show the expected output format. Follow their structure, not their content: the medications in your answer must come from the clinical note at the end of this prompt.

{EXAMPLES}


## Expected output template

Return a single valid JSON object matching the template below. Output only that object — no explanations, no surrounding text, and no markdown code fences (the fences below delimit the template and must not appear in your output).

Every medication found in the section becomes one entry in the `medications` array of that single object. Never emit more than one top-level object, and never move attribute fields out of the `attributes` object.

{EXPECTED_TEMPLATE}


## Rules

- Use `null` when a value is not stated in the text — never `""`, never `"N/A"`, including for free-text fields such as `administration_instructions`.
- Do not invent values. Only fill a field if the information is written in the note.
- **Never infer, complete or normalise a value.** With the single exception of
  `flag_is_medication_completed`, every field must be copied from text that is
  explicitly present in the note. If the information is not written there, the
  value is `null` — even when the correct value is obvious from medical knowledge.
  In particular:
  - Do not derive an active substance from a brand name, or a brand name from a
    substance (e.g. "Prilosec OTC" → `commercial_name` only, `active_substance` `null`).
  - Do not expand abbreviations, correct spelling, or normalise casing.
  - Do not infer `route` from the dosage form, or `dosage_form` from the route.
  - Do not infer `indication` from what the drug is typically prescribed for; it is
    filled only when the note states the reason for that specific medication.
  - Do not supply a customary `dose`, `quantity`, `frequency` or `duration` because
    it is the standard regimen for that drug.
  - Do not resolve ambiguous or redacted text (`___`, unexplained marks) into a
    guessed value.
- `flag_is_medication_completed` is the only field that is a judgement about the note
  rather than an extraction from it. Set it to `true` or `false` only when the note
  explicitly states that the admission medication list is complete or incomplete, and
  `null` when there is no such statement or it cannot be determined.
- Keep every extracted string exactly as it appears in the source (same casing, punctuation and spacing) so spans can be aligned to character offsets.


## Clinical note to be extracted

Clinical note to be used to extract every medication the patient was taking on admission:

{NOTE_TEXT}