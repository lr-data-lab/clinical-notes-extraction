# Zero-shot task

Extract all medications listed in the **"Medications on Admission"** section of the clinical note below.

The note is a full discharge summary — locate the admission medication section yourself and ignore every other section, including "Discharge Medications".

## Expected output

Return a **single** JSON object matching the template below exactly: the same top-level keys, the same nesting, the same key names. Every medication found in the section becomes one entry in the `medications` array. Do not return one object per medication, and do not flatten the attributes.

{EXPECTED_TEMPLATE}

## Rules

- Every key must always be present, at every level. Use `null` when a value is not stated in the text — never `""`, never `"N/A"`, including for free-text fields such as `administration_instructions` and `notes`.
- Do not invent values or keys. Only fill a field if the information is written in the note.
- If a medication line yields no attribute values at all, omit that entry rather than emitting `null` inside the array.
- If the section lists no medications, return `"medications": []`.
- Keep every span exactly as it appears in the source (same casing, punctuation and spacing) so it can be aligned to character offsets.
- Return only the JSON object. No preamble, no explanation, no markdown code fences.

## Note id

{NOTE_ID}

## Clinical note

{NOTE_TEXT}