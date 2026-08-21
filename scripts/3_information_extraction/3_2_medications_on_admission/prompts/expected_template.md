```json
{
    "medications_text": null,
    "flag_is_medication_completed": null,
    "medications": [
        {
            "span_text": "<verbatim source line>",
            "attributes": {
                "active_substance": null,
                "commercial_name": null,
                "dosage_form": null,
                "dose": [],
                "quantity": null,
                "route": null,
                "frequency": [],
                "duration": null,
                "indication": [],
                "administration_instructions": null
            }
        }
    ]
}
```

### Structural rules

- List each unique medication only once.
- The template above defines the required keys and nesting. Both the values **and the number of objects** are placeholders: replace each value with the extracted one, and emit one object per medication found — however many that is, not the single one shown.
- Return exactly these three top-level keys: `medications_text`, `flag_is_medication_completed` and `medications`. No other key.
- Each medication is an object with exactly two keys: `span_text` and `attributes`.
- The attribute fields live **inside** the `attributes` object — never at the medication's top level. They are exactly these ten, in this order: `active_substance`, `commercial_name`, `dosage_form`, `dose`, `quantity`, `route`, `frequency`, `duration`, `indication`, `administration_instructions`. All ten must be present in every medication. Do not omit keys, and do not invent keys: any key not listed above will be rejected.
- The newline character (`\n`) is prohibited in `span_text` and in all attribute values: replace any line break with a single space. `\n` is allowed exclusively in `medications_text`.
- `flag_is_medication_completed` is the one key whose `null` in the template above is also a legitimate answer. It is `null` only when the note makes no statement about the list's completeness — never by default, and never because the key was already `null` in the template.
- RULES FOR ARRAY FIELDS (dose, frequency, indication): If a dose value is unknown or redacted, output an empty list `[]`. NEVER output `null` inside a list.

Types:

- `span_text` is always present and never `null`.
- `medications_text`, `span_text`, `active_substance`, `commercial_name`, `dosage_form`,  `quantity`, `route`, `duration` and `administration_instructions`: string or `null` - not a list or an empty list.
- `flag_is_medication_completed` is the only field that is a judgement about the note rather than an extraction from it. It MUST be an unquoted JSON literal — `true`, `false` or `null`. DO NOT USE QUOTES: write true, NOT "true".
- `dose`, `frequency` and `indication`: arrays of strings, `[]` when not stated — never `null`, never a bare string. A single value is still wrapped in an array.
- `medications`: array of objects, `[]` when the section lists no medications.

### Field definitions

These five rules apply to every field below and are not repeated in each one:

1. **Verbatim, minus delimiters.** Every extracted value is copied from the note character by character — same digits, spacing, capitalisation and abbreviations. Strip outer enclosing parentheses, square brackets and introducing labels from every attribute value; punctuation inside a value (internal hyphens, slashes, ratio indicators) is retained. Nothing is lost by stripping: `span_text` preserves the source line with its delimiters.

2. **Null and empty.** A field is `null` whenever the note does not state it; for the array-valued fields the equivalent is `[]`. Only non-obvious cases are noted below.

3. **Array fields.** `dose`, `frequency` and `indication` hold one element per distinct value stated, in source order. Each element is verbatim under rule 1: the array never merges its elements into one string and never splits one expression across elements. When a line ties distinct doses to distinct administration times, `dose` and `frequency` are parallel — the *n*-th element of `frequency` is the schedule of the *n*-th element of `dose`.

4. **`dosage_form` vs `route`.** Dosage form is the physical presentation of the drug; route is the path into the body. The two are mutually exclusive, and a single line may carry both, in either order.

5. **Redactions and placeholders.** Placeholder symbols (blank lines, underlines, redaction markers, unstated-number indicators) are never valid values. If an expression is made up only of a placeholder — with or without attached units or prepositions — the attribute is unstated (`null`, or `[]` for array fields). If it mixes a visible value with a placeholder, extract only the visible component.

Top level:

- **medications_text**: the "Medications on Admission" section, verbatim, starting at the section heading itself (heading line included). Only pre-admission / home medications: if sub-sections for internal hospital status changes follow (such as "Medications on Transfer", "Inpatient Medications", "Hospital Medications" or "Discharge Medications"), truncate before they begin.

- **flag_is_medication_completed**: whether the note itself vouches for the list. `true` when the note states that the medication list is complete, accurate, verified or reconciled; `false` when it states that it is incomplete, unreliable or unverified; `null` only when the note makes no such statement at all. This statement is a sentence *about* the list rather than a medication entry, and typically sits directly under the section heading, before the entries begin — read it before extracting the entries.

- **medications**: one object per pre-admission or home medication mention. A medication administered at several times of day under a single mention remains one object; the varying doses and schedules are carried by the `dose` and `frequency` arrays. Do NOT extract medications under sub-headings for hospital care transitions, such as "Medications on Transfer", "Inpatient Medications" or "Discharge Medications".

- **span_text**: the medication mention as written. Its internal content is never altered — nothing inside is stripped, reordered, normalised or expanded, delimiters included. Only trailing material is trimmed: trailing parenthetical context that maps to no attribute, trailing list punctuation, surrounding whitespace, and stray artifact characters at the end. Preserve leading numbering when the source has it; never add numbering it does not have.

Attributes:

- **active_substance**: the chemical or generic name as written in the note. If the entry names only a brand, leave `null` — never supply the generic name from pharmacological knowledge. If more than one substance is named, extract all of them, preserving the separator used in the note. **Interleaved products:** when each substance is immediately followed by its own strength, so the names are not contiguous, join the names in source order with the separator that appears between them, omitting the intervening strengths and copying the separator's spacing exactly. This is the only case in which a value is assembled from non-contiguous text.

- **commercial_name**: brand or trade name, including descriptive over-the-counter product names and proprietary device delivery systems. A release modifier or strength designation that forms part of the registered brand name stays inside `commercial_name` and is not repeated elsewhere. `null` if only the active substance is mentioned.

- **dosage_form**: the physical presentation of the drug, plus infusion modes and release modifiers stated independently of a brand name. Always extract it when present, even if the same form word also appears inside the `quantity` string. Exception: a brand or proprietary device name belongs to `commercial_name` and is not repeated here, leaving `dosage_form` `null`.

- **dose**: array of measured amounts representing the medication's stated strength or concentration, or another explicitly stated measured dose amount. A strength or concentration stated with the active substance or medication name is always extracted as `dose`, even when it describes the marketed product and even when the medication is administered as a discrete unit. Units of mass, volume, concentration, molar amount, biological potency, infusion rate, or device size or gauge belong to `dose`. An amount whose unit names a discrete countable form or actuation instead belongs to `quantity`. Never classify a countable administered unit such as a drop, tablet, capsule, puff, spray, patch, vial, or ampoule as `dose`. Never include count units, route, or schedule markers in `dose`. An explicit statement that the dose or strength is unknown or unverified yields `[]`. One element per distinct measured amount, however much internal structure each has — combination and multiphasic products keep the whole expression together, per-phase counts included, and are never split. Infusion rates keep their time denominator: the exclusion of frequency refers to schedule markers, not rate denominators. **Interleaved products:** when each strength is stated immediately after its own substance, so the strengths are not contiguous, join them in source order into a **single element**, using the separator that appears between them and copying its spacing exactly.

- **quantity**: the number of discrete units administered at one time, written as a number followed by a **count unit**. A count unit names a discrete, countable form, item, or actuation in which the medication is dispensed or delivered, rather than measuring the amount of active substance it contains. Quantity therefore represents how many discrete units are administered, while `dose` represents the medication's strength, concentration, or other measured amount. Units of mass, volume, concentration, molar amount, and biological potency belong to `dose`, not `quantity`, even when the unit wording contains a count-related term. Never infer `quantity` from a measured amount alone. Never include the schedule or frequency in `quantity`. `quantity` is a single string, never an array. It must contain both a number and a count unit; a bare number or bare count unit is not a valid quantity. When different quantities are specified for different administration times, leave `quantity` as `null` rather than selecting or combining them. When the quantity is redacted, unspecified, or otherwise not explicitly stated, use `null`. When `quantity` is present, `dose` should independently contain the medication's stated strength or concentration when available; the presence of `quantity` does not replace or suppress `dose`. Not a list or an empty list.

- **route**: the path by which the drug enters the body, exactly as it appears in the note, abbreviated or not. Not to be confused with `dosage_form`; a single line may carry both. `null` when no route is stated.

- **frequency**: array of schedule expressions governing administration, each verbatim and without the dose amount or the route. Meal times, times of day and recurring daily events are schedule information and belong here, whether written inline or in parentheses attached to a dose. One element per distinct schedule stated, in source order, parallel to `dose` per rule 3.

- **duration**: the length of the treatment period, exactly as written. `null` if not stated.

- **indication**: array of clinical reasons or triggering conditions for administering the drug — the "why", most commonly found after a PRN marker and its colon separator. Annotate each span literally, preserving severity qualifiers as written; normalisation is a downstream task. The PRN marker itself belongs to `frequency`. One element per distinct reason stated.

- **administration_instructions**: free-text directions constraining how or under what conditions the drug is given — hold parameters, intake conditions, titration rules, application sites. An indication triggers administration; an instruction constrains it. Exclude trailing parenthetical context that maps to no attribute.