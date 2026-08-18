# Task

Extract all medications listed in the **"Medications on Admission"** section of the clinical note below.

The note is a full discharge summary — locate the admission medication section yourself and ignore every other section, including "Discharge Medications".

## Expected output template

Return a single valid JSON object matching the template below. Output only that object without any introductory text, explanations, or commentary.

Every medication found in the section becomes one entry in the `medications` array of that single object. Never emit more than one top-level object, and never move attribute fields out of the `attributes` object.

{EXPECTED_TEMPLATE}

## Rules

- Use `null` when a value is not stated in the text — never `""`, never `"N/A"`, including for free-text fields such as `administration_instructions`.
- Do not invent values. Only fill a field if the information is written in the note.
- Keep every extracted string exactly as it appears in the source (same casing, punctuation, and spacing) so spans can be aligned to character offsets.
- Replace any newline character (\n) inside extracted attribute values or `span_text` with a single space. Newline characters are permitted only in `medications_text`.

## Clinical note

Clinical note to be used to extract every medication the patient was taking on admission:

{NOTE_TEXT}