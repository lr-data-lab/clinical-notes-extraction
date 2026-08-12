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

1. **Verbatim.** Every extracted value is a contiguous substring of the note, copied character by character — same digits, spacing, capitalisation and abbreviations. No conversion, expansion or reformatting.
2. **Null.** A field is `null` whenever the note does not state it (`[]` for `indication`). Only non-obvious null cases are noted below.
3. **`dosage_form` vs `route`.** Dosage form is the physical presentation of the drug; route is the path into the body. `PO`, `IV`, `SC`, `IM`, `PR`, `SL`, `TP` and `Ophth.` are routes and never dosage forms. One line may carry both, in either order: `Ondansetron ODT 4 mg PO Q8H` → dosage_form `ODT`, route `PO`; `Latanoprost 0.005% Ophth. Soln.` → route `Ophth.`, dosage_form `Soln.`

Top level:

- **medications_text** — the whole "Medications on Admission" section.
- **flag_is_medication_completed** — `false` if the note says the list is incomplete or unreliable ("unable to verify"); `true` if it says the list is complete ("The Preadmission Medication list is accurate and complete."); `null` if it says neither.
- **medications** — one object per medication mention; `[]` if the section lists none ("None"). One source line describing one drug stays one object even with two regimens (e.g. a morning and an evening dose): keep the full expression in `dose` and `frequency` instead of splitting.
- **span_text** — the medication mention. Keep leading list numbering (`1. Aspirin 81 mg PO DAILY`). Exclude trailing parenthetical context that maps to no attribute (`(last dose charted at 1600 ___)`).

Attributes:

- **active_substance** — generic or chemical name. Never derived from a brand: `Prilosec OTC` → `null`. A component spelled out inside a descriptive product name belongs here: `artificial Tear with Lanolin` → `Lanolin`.
- **commercial_name** — brand or trade name, including descriptive OTC product names (`artificial Tear with Lanolin`).
- **dosage_form** — tablet, capsule, cream, `Soln.`, `ODT`. Also infusion modes (`drip`, `gtt`, `infusion`) and release modifiers (`ER`, `XR`, `XL`, `SR`, `CR`, `LA`, `Extended-Release`, `Sustained-Release`): `Diltiazem Extended-Release 120 mg` → `Extended-Release`. Exception: a modifier belonging to a registered brand stays in `commercial_name` and is not repeated here — `Toprol XL 50 mg` → commercial_name `Toprol XL`, dosage_form `null`.
- **dose** — mass, volume or concentration with its unit. Meaning depends on `quantity`: when `quantity` is `null`, the amount given at one time (`Amiodarone 100 mg PO DAILY` → `100 mg`); when `quantity` is filled, the strength per unit (`Fluticasone Propionate 110mcg 2 PUFF` → `110mcg`). Combination and multiphasic products keep the whole expression, per-phase counts included: `0.15 mg-30 mcg (84)/10 mcg (7)`, `250-100 mg-unit`. Infusion rates are kept whole with their time denominator (`10 mcg/hr`, `250 mL/hr`) — the exclusion of frequency refers to schedule markers (`BID`, `Q8H`), not to rate denominators. Never count units, route or schedule. Null when no mass, volume or concentration is stated (`Albuterol Inhaler 2 PUFF IH` → `null`) and when the number is redacted even if the unit shows (`Vitamin D "___" UNIT` → `null`).
- **quantity** — number of discrete units given at one time, with its count unit: `2 PUFF`, `1 DROP`, `1 TAB` (also `CAP`, `SPRAY`, `PATCH`, `SUPP`). Never inferred: `Amiodarone 100 mg` → `null`, even though it is implicitly one tablet. Never carries frequency.
- **route** — the abbreviation as written.
- **frequency** — the schedule only: `DAILY`, `BID`, `Q6H:PRN`, `at bedtime`. Carries neither the dose nor the route — in `100 mg PO DAILY` the frequency is `DAILY`, not `PO DAILY`.
- **duration** — length of treatment (`for 7 days`, `x 2 weeks`), without the `Duration:` label where the source uses one.
- **indication** — the reason or triggering condition for giving the drug. Usually after a PRN marker, past the colon where present (`Q6H:PRN pain` → `pain`). Keep severity qualifiers as written (`Pain - Mild`, not `pain`); normalisation is a downstream task. Excludes the PRN marker itself, which is frequency. One array element per distinct reason.
- **administration_instructions** — free-text directions constraining how or under what conditions the drug is given: hold parameters (`hold for sbp<100`), intake conditions (`take with food`, `do not crush`), titration rules (`titrate to effect`, `per sliding scale`), application sites (`to affected area`, `both eyes`). An indication triggers administration; an instruction constrains it.