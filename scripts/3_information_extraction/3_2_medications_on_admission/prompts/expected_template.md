```json
{
    "medications_text": null,
    "flag_is_medication_completed": null,
    "medications": [
        {
            "span_text": null,
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

- The template above defines the required keys and nesting. Both the values **and the number of objects** are placeholders: replace each value with the extracted one, and emit one object per medication found — however many that is, not the single one shown.
- Return exactly these three top-level keys: `medications_text`, `flag_is_medication_completed` and `medications`. Do not add any other key.
- Each medication is an object with exactly two keys: `span_text` and `attributes`.
- The attribute fields live **inside** the `attributes` object — never at the medication's top level. They are exactly these, in this order: `active_substance`, `commercial_name`, `dosage_form`, `dose`, `quantity`, `route`, `frequency`, `duration`, `indication`, `administration_instructions`.
- All ten attribute keys must be present in every medication. Do not omit keys, and do not invent keys: any key not listed above will be rejected.
- Line Break / Newline Handling: The newline character (`\n`) is strictly prohibited in `span_text` and all `attributes` fields. Replace any newline or line break within `span_text` or attribute strings with a single space. `\n` is allowed exclusively in `medications_text`.

Types:

- `medications_text` and all attributes except `dose`, `frequency` and `indication`: string or `null`
- `span_text`: string — always present, never `null`
- `flag_is_medication_completed`: the JSON literal `true`, `false` or `null` — never a string
- `dose`, `frequency` and `indication`: arrays of strings, `[]` when the field is not stated — never `null`, and never a bare string. A single value is still wrapped in an array.
- `medications`: array of objects, `[]` when the section lists no medications

### Field definitions

These four rules apply to every field below and are not repeated in each one:

1. **Verbatim, minus delimiters.** Every extracted value is copied from the note character by character — same digits, spacing, capitalisation and abbreviations.
Enclosing Delimiters Rule: Strip outer enclosing parentheses (), square brackets [], and introducing labels from ALL extracted attribute values (including dose, commercial_name, dosage_form, route, frequency, indication, duration, quantity, active_substance, and administration_instructions). Punctuation inside a value (e.g., internal hyphens, slashes, ratio indicators like 250/50) is retained.
Fidelity via span_text: Fidelity to the source line is preserved by span_text, which always retains the original text unchanged, delimiters included — so nothing is lost by stripping outer brackets or parentheses from attribute values.

2. **Null and empty.** A field is `null` whenever the note does not state it. For the array-valued fields the equivalent is the empty array `[]`. Only non-obvious cases are noted below.

3. **Array fields.** `dose`, `frequency` and `indication` hold one array element per distinct value stated in the note. Each element is verbatim under rule 1; the array is a container and never merges its elements into a single string, and never splits a single expression across elements. Elements appear in the order in which they occur in the source text. When a line ties distinct doses to distinct administration times, `dose` and `frequency` are parallel: the *n*-th element of `frequency` is the schedule of the *n*-th element of `dose`. When a single schedule governs a single dose, both arrays hold one element each.

4. **`dosage_form` vs `route`.** Dosage form is the physical presentation of the drug; route is the path into the body. The two are mutually exclusive: an expression denoting a route is never annotated as a dosage form, and an expression denoting a physical presentation is never annotated as a route. A single line may carry both, in either order.

5. **Redactions and Placeholders.** Placeholder symbols (such as blank lines, underlines, redaction markers, or unstated number indicators) are never valid extracted values. Fully Redacted Fields: When a field or expression contains only a placeholder symbol (with or without attached units or prepositions), treat the attribute as unstated. Assign null for scalar fields and [] for array fields. Partially Redacted Fields: When an expression contains both a valid, visible value and a placeholder symbol, extract only the valid visible component verbatim, omitting the placeholder.

Top level:

- **medications_text**: the "Medications on Admission" section, verbatim. Only include pre-admission / home medications. If the text contains subsequent sub-sections for internal hospital status changes (such as "Medications on Transfer", "Inpatient Medications", "Hospital Medications", or "Discharge Medications"), truncate medications_text before those sub-sections begin.

- **flag_is_medication_completed**: `false` if the note says the list is incomplete or unreliable; `true` if it says the list is complete; `null` if it says neither.

- **medications**: one object per pre-admission or home medication mention. A medication administered at several times of day under a single mention remains one object; the varying doses and schedules are carried by the `dose` and `frequency` arrays. Do NOT extract medications listed under sub-headings for hospital care transitions, such as "Medications on Transfer", "Inpatient Medications", or "Discharge Medications". Ignore all lines belonging to those sub-sections.

- **span_text**: the medication mention, kept exactly as written in the source text. Preserve leading numbering only if it is present in the original line; never add numbering that the source does not have. Exclude trailing parenthetical context that maps to no attribute. Rule 1 does not apply here: span_text is never stripped of anything internal. Do not include trailing list punctuation (commas, semicolons), leading or trailing whitespace, or artifact characters (such as double quotes or apostrophes) at the end of span_text.

Attributes:

- **active_substance**: the chemical name or generic name in the source text. If the entry names only a brand, leave null — do not supply the chemical name or generic name from pharmacological knowledge. If the entry names more than one active substance, extract all of them, preserving the separator used in the note.

- **commercial_name**: brand or trade name, including descriptive over-the-counter product names and proprietary device delivery systems. Where a release modifier or a strength designation forms part of the registered brand name, it is kept inside commercial_name and is not repeated in any other field. Null if only the active substance is mentioned. Strip outermost delimiters and labels per rule 1.

- **dosage_form**: the physical presentation of the drug. Also infusion modes and release modifiers stated independently of a brand name. Enclosing parentheses are delimiters and are stripped (rule 1). Exception: a brand or proprietary device name belongs to commercial_name and is not repeated here, leaving dosage_form null. Always extract the dosage form whenever present in the text, even if the same form word also appears inside the quantity string.

- **dose**: array of mass, volume, concentration, potency, or medical device size or gauge expressions with their units. One element per distinct dose stated for the medication: a single dose yields a one-element array, and a regimen stating different amounts at different administration times yields one element per amount, in source order. An explicit statement that the dose is unknown or unverified yields `[]`, however phrased.
Meaning depends on quantity: when quantity is null, a dose element is the amount given at one time; when quantity is filled, it is the strength per unit.
Product description is not a dose. Where a line states the concentration or pack volume of the marketed product alongside the amount the patient takes, only the amount taken is extracted; the product's concentration and pack volume are not annotated. Fidelity to the full line is preserved by `span_text`.
A single dose expression is one element, however much internal structure it has: combination and multiphasic products keep the whole expression together, per-phase counts included, and are never split across elements.
Infusion rates are kept whole with their time denominator — the exclusion of frequency refers to schedule markers, not to rate denominators. Never count units, route or schedule.
If a dose expression is partially redacted, extract only the valid visible dose or size component; if the entire dose is redacted, it contributes no element. Strip outermost brackets and parentheses per rule 1.

- **quantity**: how many discrete units are administered at one time, written as a number followed by a **count unit** — a unit naming a countable physical form of the product. Never output a bare number without a unit.
Count units only. Units of mass, volume, molar amount and biological potency measure how much of the substance is given, not how many forms of it, and belong to dose. This holds regardless of what else the line states: a line whose only administered amount is expressed in such units leaves quantity null and puts that amount in dose.
Never inferred: a line stating only an amount leaves quantity null, even though one countable unit may be implied.
Redacted number → null. A bare unit with no number is not a quantity.
Never carries the schedule: the schedule marker belongs to frequency.
Never free text: a statement that the dose is unknown is a statement about the dose, not a count, and leaves quantity null and `dose` empty.
When quantity is filled, dose holds the strength per unit.
Does not exclude dosage_form: extracting a count unit in quantity does not prevent extracting the corresponding physical form in dosage_form. Both fields are populated concurrently.

- **route**: the route of administration — the path by which the drug enters the body. Annotate the expression exactly as it appears in the source text, abbreviated or not. Do not confuse with dosage_form, which describes the physical presentation of the drug. A single line may carry both. Null when no route is stated.

- **frequency**: array of schedule expressions governing administration, each verbatim and without the dose amount or the administration route. Meal times, times of day and recurring daily events are schedule information and belong here, whether written inline or enclosed in parentheses attached to a dose; enclosing parentheses are delimiters and are stripped per rule 1. One element per distinct schedule stated, in source order, parallel to `dose` per rule 3. `[]` when no schedule is stated.

- **duration**: the length of the treatment period, exactly as written in the note. Null if not stated.

- **indication**: array of clinical reasons or triggering conditions for administering the drug — the "why". Most commonly found after a PRN marker, following the colon separator where present. Annotate each span literally, preserving severity qualifiers as written; normalisation is a downstream task. Do not include the PRN marker itself, which belongs to frequency. One element per distinct reason stated. `[]` when no indication is stated.

- **administration_instructions**: free-text directions constraining how or under what conditions the drug is given: hold parameters, intake conditions, titration rules, application sites. An indication triggers administration; an instruction constrains it. Exclude trailing parenthetical context that maps to no attribute.