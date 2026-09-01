# Task

Extract all medications listed in the **"Medications on Admission"** section of the clinical note below.

The note is a full discharge summary — locate the admission medication section yourself and ignore every other section, including any section covering hospital care transitions such as "Inpatient Medications", "Hospital Medications" or "Discharge Medications".


## Expected output template

Return a single valid JSON object strictly matching the template and structure shown below. Output ONLY that JSON object: no introductory text, no post-extraction explanation and no markdown code fences around it. The template below is shown inside a code fence for readability only — your answer must begin with `{` and end with `}`.

Every medication found in the section becomes one entry in the `medications` array of that single top-level object. Never emit more than one top-level JSON object, and never move attribute fields out of the nested `attributes` object.

{EXPECTED_TEMPLATE}

- Do not invent values. Only fill a field if the information is written in the note. **Never infer, complete or normalise a value**, except where the template declares otherwise.


## Clinical note to be extracted

Clinical note to be used to extract every medication the patient was taking on admission:

{NOTE_TEXT}