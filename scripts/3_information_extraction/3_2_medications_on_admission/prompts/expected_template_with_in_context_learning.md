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
                "dose": null,
                "quantity": null,
                "route": null,
                "frequency": null,
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

- `medications_text` and all attributes except `indication`: string or `null`
- `span_text`: string — always present, never `null`
- `flag_is_medication_completed`: the JSON literal `true`, `false` or `null` — never a string
- `indication`: array of strings, `[]` when no indication is stated — even for a single value: `["pain"]`, not `"pain"`
- `medications`: array of objects, `[]` when the section lists no medications

### Field definitions

These three rules apply to every field below and are not repeated in each one:

1. **Verbatim, minus delimiters.** Every extracted value is copied from the note character by character — same digits, spacing, capitalisation and abbreviations. Mixed-case brand-safety spellings are kept exactly as written: `OxycoDONE` stays `OxycoDONE`, `HydrOXYzine` stays `HydrOXYzine`. No conversion, expansion or reformatting.

  The single exception is **delimiting punctuation**: characters or labels the note uses to set a value apart from the surrounding text, as opposed to punctuation that belongs to the value itself. Strip the outermost delimiters and any introducing label; keep everything inside.
  - (250/50) → dose 250/50, not (250/50)
  - `DONEPEZIL [ARICEPT]` → commercial_name `ARICEPT`, not `[ARICEPT]`
  - `OxycoDONE (Immediate Release)` → dosage_form `Immediate Release`, not `(Immediate Release)`
  - `Duration: 7 Days` → duration `7 Days`, not `Duration: 7 Days`

  Punctuation that is part of the value stays untouched: `Alum-Mag Hydroxide-Simethicone`, `Q6H:PRN`, `0.15 mg-30 mcg`, `0.5%`, `250-100 mg-unit`.Brackets forming part of a registered brand name are likewise kept.

  Fidelity to the source line is preserved by `span_text`, which always retains the original text unchanged, delimiters included — so nothing is lostby stripping them from the attribute values.

2. **Null.** A field is `null` whenever the note does not state it (`[]` for `indication`). Only non-obvious null cases are noted below.
3. **`dosage_form` vs `route`.** Dosage form is the physical presentation of the drug; route is the path into the body. `PO`, `IV`, `SC`, `IM`, `PR`, `SL`, `TP` and `Ophth.` are routes and never dosage forms. One line may carry both, in either order: `Ondansetron ODT 4 mg PO Q8H` → dosage_form `ODT`, route `PO`; `Latanoprost 0.005% Ophth. Soln.` → route `Ophth.`, dosage_form `Soln.`

Top level:

- **medications_text**: the "Medications on Admission" section, verbatim. Only include pre-admission / home medications. If the text contains subsequent sub-sections for internal hospital status changes (such as "Medications on Transfer", "Inpatient Medications", "Hospital Medications", or "Discharge Medications"), truncate medications_text before those sub-sections begin.

- **flag_is_medication_completed**: `false` if the note says the list is incomplete or unreliable ("unable to verify"); `true` if it says the list is complete ("The Preadmission Medication list is accurate and complete."); `null` if it says neither.

- **medications**: one object per pre-admission or home medication mention. Do NOT extract medications listed under sub-headings for hospital care transitions, such as "Medications on Transfer", "Inpatient Medications", or "Discharge Medications". Ignore all lines belonging to those sub-sections.

- **span_text**: the medication mention, kept exactly as written in the source text. Preserve leading numbering ONLY if it is present in the original line (e.g., "1. Aspirin 81 mg PO DAILY" retains "1.", but "aspirin 325 daily" stays "aspirin 325 daily" without adding any number). Exclude trailing parenthetical context that maps to no attribute ("(last dose charted at 1600 ___)"). Rule 1 does not apply here: span_text is never stripped of anything internal. Do not include trailing list punctuation (commas, semicolons) or artifact characters (such as double quotes or apostrophes '') at the end of span_text.


Attributes:

- **active_substance**: the chemical name or generic name in the source text. If the entry names only a brand, leave null — do not supply the chemical name or generic name from pharmacological knowledge. If there are 2 active substance extract both e.g. `Latanoprost 0.005% / Timolol 0.5%` -> `Latanoprost / Timolol`

- **commercial_name**: brand or trade name, including descriptive OTC product names (artificial Tear with Lanolin) and proprietary device delivery systems (e.g., Diskus, Handihaler, Turbuhaler, Flexhaler, Evohaler). Null if only the active substance is mentioned. Strip outermost delimiters and labels per rule 1.

- **dosage_form**: physical presentation of the drug (tablet, capsule, cream, Soln., ODT, CAP, TAB). Also infusion modes (drip, gtt, infusion) and release modifiers (ER, XR, XL, SR, CR, LA, Extended-Release, Sustained-Release, Immediate Release). Enclosing parentheses are delimiters and are stripped (rule 1). Exception: a brand or proprietary device name (e.g., Diskus) belongs to commercial_name and is not repeated here, leaving dosage_form null. Always extract the dosage form (e.g., TAB, CAP) whenever present in the text, even if it is also included within the quantity string (e.g., for "1 TAB", set dosage_form to "TAB" and quantity to "1 TAB").

- **dose**: mass, volume, concentration, or medical device size/gauge with its unit (e.g., 100 mg, 110mcg, 29 gauge, 5 mm). An explicit statement that the dose is unknown or unverified is null, however phrased — Dosage uncertain, Dose is Unknown, dose unclear. Meaning depends on quantity: when quantity is null, the amount given at one time (Amiodarone 100 mg PO DAILY → 100 mg); when quantity is filled, the strength per unit (Fluticasone Propionate 110mcg 2 PUFF → 110mcg). Combination and multiphasic products keep the whole expression, per-phase counts included: 0.15 mg-30 mcg (84)/10 mcg (7), 250-100 mg-unit. Infusion rates are kept whole with their time denominator (10 mcg/hr, 250 mL/hr) — the exclusion of frequency refers to schedule markers (BID, Q8H), not to rate denominators. Never count units, route or schedule. If a dose expression is partially redacted (e.g., "29 gauge x ___"), extract only the valid visible dose/size component ("29 gauge"); if the entire dose is redacted (e.g., "___ mg"), set to null. Strip outermost brackets/parentheses per rule 1.

- **quantity**: how many discrete units are administered at one time, written as a number followed by a count unit: 2 PUFF, 1 DROP, 1 TAB, 1 INH (also CAP, SPRAY, PATCH, SUPP, LOZENGE). Never output a bare number without a unit (e.g., "1 INH", never "1").
Never inferred: Amiodarone 100 mg → null, even though one tablet is implied.
Count units only. Units of biological potency measure strength, not countable forms, and belong to dose: Humalog 20 Units → dose 20 Units, quantity null. Same for UNIT, mEq, mcg, mg, mL.
Redacted number → null. A bare unit with no number is not a quantity.
Never carries the schedule: 2 PUFF QID → quantity 2 PUFF, frequency QID.
Never free text: Dose is Unknown is a statement about the dose, not a count, and leaves both dose and quantity null.
When quantity is filled, dose holds the strength per unit: Fluticasone Propionate 110mcg 2 PUFF → dose 110mcg, quantity 2 PUFF.
Does not exclude dosage_form: Extracting a count unit in quantity (e.g., "1 TAB") does not prevent extracting the corresponding physical form in dosage_form (e.g., dosage_form: "TAB"). Both fields should be populated concurrently.
    
- **route**: The route of administration — the path by which the drug enters the body (e.g. `topical`, `oral`). Annotate the abbreviation exactly as it appears in the source text. Do not confuse with dosage_form, which describes the physical presentation of the drug (tablet, capsule, solution, patch). A single line may carry both (Ondansetron 4 mg IV ODT → route IV, dosage form ODT). Null when no route is stated.

- **frequency**: The frequency and schedule of administration (e.g., "Daily", "BID", "PRN", "Q8H", "at bedtime"), exactly as written in the note, without the dose amount or the administration route. Null if not stated.

- **duration**: The length of the treatment period (e.g., "for 7 days", "x 2 weeks"), exactly as written in the note. Null if not stated.

- **indication**: The clinical reason or triggering condition for administering the drug — the "why". Most commonly found after a PRN marker, following the colon separator where present (Q6H:PRN pain → pain). Annotate the span literally, preserving severity qualifiers as written (Pain - Mild, not pain); normalisation is a downstream task. Do not include the PRN marker itself, which belongs to frequency. Always an array of strings, with one element per distinct reason stated. Empty array [] when no indication is stated

- **administration_instructions**: free-text directions constraining how or under what conditions the drug is given: hold parameters (`hold for sbp<100`), intake conditions (`take with food`, `do not crush`), titration rules (`titrate to effect`, `sliding scale`), application sites (`to affected area`, `both eyes`). An indication triggers administration; an instruction constrains it. Exclude trailing parenthetical context that maps to no attribute (`(last dose charted at 1600 ___)`).