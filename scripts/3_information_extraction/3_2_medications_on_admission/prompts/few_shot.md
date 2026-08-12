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
- Keep every extracted string exactly as it appears in the source (same casing, punctuation and spacing) so spans can be aligned to character offsets.

## Clinical note

Clinical note to be used to extract every medication the patient was taking on admission:

{NOTE_TEXT}