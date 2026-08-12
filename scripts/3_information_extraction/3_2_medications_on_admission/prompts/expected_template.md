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

   - `DONEPEZIL [ARICEPT]` → commercial_name `ARICEPT`, not `[ARICEPT]`
   - `OxycoDONE (Immediate Release)` → dosage_form `Immediate Release`, not `(Immediate Release)`
   - `Duration: 7 Days` → duration `7 Days`, not `Duration: 7 Days`

   Punctuation that is part of the value stays untouched: `Alum-Mag Hydroxide-Simethicone`, `Q6H:PRN`, `0.15 mg-30 mcg`, `0.5%`, `250-100 mg-unit`. Brackets forming part of a registered brand name are likewise kept.

   Fidelity to the source line is preserved by `span_text`, which always retains the original text unchanged, delimiters included — so nothing is lost by stripping them from the attribute values.

2. **Null.** A field is `null` whenever the note does not state it (`[]` for `indication`). Only non-obvious null cases are noted below.
3. **`dosage_form` vs `route`.** Dosage form is the physical presentation of the drug; route is the path into the body. `PO`, `IV`, `SC`, `IM`, `PR`, `SL`, `TP` and `Ophth.` are routes and never dosage forms. One line may carry both, in either order: `Ondansetron ODT 4 mg PO Q8H` → dosage_form `ODT`, route `PO`; `Latanoprost 0.005% Ophth. Soln.` → route `Ophth.`, dosage_form `Soln.`

Top level:

- **medications_text**: the whole "Medications on Admission" section, verbatim, including the completeness statement when present. Always start with "Medications on Admission:".

- **flag_is_medication_completed**: `false` if the note says the list is incomplete or unreliable ("unable to verify"); `true` if it says the list is complete ("The Preadmission Medication list is accurate and complete."); `null` if it says neither.

- **medications**: one object per medication mention; `[]` if the section lists none ("None"). One source line describing one drug stays one object even with two regimens (e.g. a morning and an evening dose): keep the full expression in `dose` and `frequency` instead of splitting.

- **span_text**: the medication mention, kept exactly as written. Keep leading list numbering (`1. Aspirin 81 mg PO DAILY`). Exclude trailing parenthetical context that maps to no attribute (`(last dose charted at 1600 ___)`). Rule 1 does not apply here: `span_text` is never stripped of anything internal.


Attributes:

- **active_substance**: the generic/chemical name as written in the source text. If the entry names only a brand, leave null — do not supply the generic from pharmacological knowledge.
  "Toprol XL 50mg daily"  -> active_substance: null, commercial_name: "Toprol XL"
  "Lisinopril 10mg daily" -> active_substance: "Lisinopril", commercial_name: null

- **commercial_name**: brand or trade name, including descriptive OTC product names (`artificial Tear with Lanolin`). Enclosing brackets are delimiters, not part of the name (rule 1).

- **dosage_form**: tablet, capsule, cream, `Soln.`, `ODT`. Also infusion modes (`drip`, `gtt`, `infusion`) and release modifiers (`ER`, `XR`, `XL`, `SR`, `CR`, `LA`, `Extended-Release`, `Sustained-Release`, `Immediate Release`): `Diltiazem Extended-Release 120 mg` → `Extended-Release`. Enclosing parentheses are delimiters and are stripped (rule 1). Exception: a modifier belonging to a registered brand stays in `commercial_name` and is not repeated here — `Toprol XL 50 mg` → commercial_name `Toprol XL`, dosage_form `null`.

- **dose**: mass, volume or concentration with its unit. An explicit statement that the dose is unknown or unverified is null, however phrased — Dosage uncertain, Dose is Unknown, dose unclear. Meaning depends on `quantity`: when `quantity` is `null`, the amount given at one time (`Amiodarone 100 mg PO DAILY` → `100 mg`); when `quantity` is filled, the strength per unit (`Fluticasone Propionate 110mcg 2 PUFF` → `110mcg`). Combination and multiphasic products keep the whole expression, per-phase counts included: `0.15 mg-30 mcg (84)/10 mcg (7)`, `250-100 mg-unit`. Infusion rates are kept whole with their time denominator (`10 mcg/hr`, `250 mL/hr`) — the exclusion of frequency refers to schedule markers (`BID`, `Q8H`), not to rate denominators. Never count units, route or schedule. When the number is redacted but the unit shows, must extract the unit (`Vitamin D "___" UNIT` → `UNIT`).

- **quantity**: number of discrete units given at one time, with its count unit: `2 PUFF`, `1 DROP`, `1 TAB` (also `CAP`, `SPRAY`, `PATCH`, `SUPP`). Never inferred: `Amiodarone 100 mg` → `null`, even though it is implicitly one tablet. Never carries frequency. . When the number is redacted but the unit shows, must extract the unit (`"___" PUFF` → `PUFF`). Always a number followed by a count unit. Free text is never a quantity: a phrase such as Dose is Unknown is a statement about the dose, not a count, and leaves both dose and quantity null.

- **route**: the abbreviation as written.

- **frequency**: the schedule only: `DAILY`, `BID`, `Q6H:PRN`, `at bedtime`. Carries neither the dose nor the route — in `100 mg PO DAILY` the frequency is `DAILY`, not `PO DAILY`.

- **duration**: length of treatment (`for 7 days`, `x 2 weeks`), without the `Duration:` label where the source uses one (rule 1).

- **indication**: the reason or triggering condition for giving the drug. Usually after a PRN marker, past the colon where present (`Q6H:PRN pain` → `pain`). Keep severity qualifiers as written (`Pain - Mild`, not `pain`); normalisation is a downstream task. Excludes the PRN marker itself, which is frequency. One array element per distinct reason.

- **administration_instructions**: free-text directions constraining how or under what conditions the drug is given: hold parameters (`hold for sbp<100`), intake conditions (`take with food`, `do not crush`), titration rules (`titrate to effect`, `per sliding scale`), application sites (`to affected area`, `both eyes`). An indication triggers administration; an instruction constrains it. Exclude trailing parenthetical context that maps to no attribute (`(last dose charted at 1600 ___)`).