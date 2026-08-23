```json
{
    "medications_text": "<string|null>",
    "flag_is_medication_completed": <true|false|null>,
    "medications": [
        {
            "span_text": "<string>",
            "attributes": {
                "active_substance": "<string|null>",
                "commercial_name": "<string|null>",
                "dosage_form": "<string|null>",
                "dose": [],
                "quantity": "<string|null>",
                "route": "<string|null>",
                "frequency": [],
                "duration": "<string|null>",
                "indication": [],
                "administration_instructions": "<string|null>"
            }
        }
    ]
}
```

### Structural rules

- List each unique medication only once.
- The skeleton above defines the required keys, their nesting and their types. `"<string|null>"` is a type annotation, not an answer: it marks a field holding a single string or `null` — never a list — and the angle brackets never appear in the output. `<true|false|null>` marks an unquoted JSON literal. The array fields are shown empty, which is both their type and their answer when the note states nothing: fill each with one element per value stated, and leave it `[]` otherwise — never insert an empty or `null` element to occupy the position. The number of medication objects is illustrative: emit one per medication found, however many that is, not the single one shown. A placeholder is never itself an answer.
- Return exactly these three top-level keys: `medications_text`, `flag_is_medication_completed` and `medications`. No other key.
- Each medication is an object with exactly two keys: `span_text` and `attributes`.
- The attribute fields live **inside** the `attributes` object — never at the medication's top level. They are exactly these ten, in this order: `active_substance`, `commercial_name`, `dosage_form`, `dose`, `quantity`, `route`, `frequency`, `duration`, `indication`, `administration_instructions`. All ten must be present in every medication. Do not omit keys, and do not invent keys: any key not listed above will be rejected.
- The newline character (`\n`) is prohibited in `span_text` and in all attribute values: replace any line break with a single space. `\n` is allowed exclusively in `medications_text`.
- `null` is a legitimate answer for two kinds of field. `flag_is_medication_completed` is `null` only when the note makes no statement about the list's completeness — never by default. Every scalar attribute is `null` when the note does not state it. `span_text` is not one of these: it is always present and is never `null`.
- An empty string (`""`) is never a valid value for any field. A scalar field that the note does not state is `null`; an array field that the note does not state is `[]`.

### Types

- **Scalar fields** — `medications_text`, `span_text`, `active_substance`, `commercial_name`, `dosage_form`, `quantity`, `route`, `duration` and `administration_instructions`: each holds a single string, or `null` where the rules allow it. A scalar value is **never** wrapped in an array: a single value is written as the string itself, not as a one-element list. This holds for all nine without exception, including short codes and abbreviations. Not a list, not an empty list, not an empty string.
- `span_text` is always present and never `null`.
- **Array fields** — `dose`, `frequency` and `indication`: arrays of strings, `[]` when not stated. Never `null`, never a bare string; a single value is still wrapped in an array. An element is never `null` and never an empty string: if a value is unknown or redacted, the array is `[]` rather than holding an empty placeholder.
- `flag_is_medication_completed` is the only field that is a judgement about the note rather than an extraction from it. It must be an unquoted JSON literal — `true`, `false` or `null`. **Never quoted**: write `true`, not `"true"`.

### General rules

These rules apply to every field below and are not repeated in each one:

1. **Verbatim, minus delimiters.** Every extracted value is copied from the note character by character — same digits, spacing, capitalisation and abbreviations. The single exception is the newline substitution required in the structural rules above. Strip outer enclosing parentheses, square brackets and introducing labels from every attribute value; punctuation inside a value (internal hyphens, slashes, ratio indicators) is retained. Nothing is lost by stripping: `span_text` preserves the source line with its delimiters.

2. **Null and empty.** A field is `null` whenever the note does not state it; for the array-valued fields the equivalent is `[]`. Only non-obvious cases are noted below.

3. **Never infer, complete or normalise a value.** Every field is copied from text that is explicitly present in the note, with two declared exceptions: `flag_is_medication_completed`, which is a judgement about the note rather than an extraction from it; and the interleaved-product case described below, where a value is assembled from non-contiguous text. Outside those two, if the information is not written in the note the field is unstated — even when the correct value is obvious from medical knowledge. In particular:
   - Do not derive an active substance from a brand name, or a brand name from a substance.
   - Do not expand abbreviations, correct spelling, or normalise casing.
   - Do not infer `route` from the dosage form, or `dosage_form` from the route.
   - Do not infer `indication` from what the drug is typically prescribed for; it is filled only when the note states the reason for that specific medication.
   - Do not supply a customary `dose`, `quantity`, `frequency` or `duration` because it is the standard regimen for that drug.

4. **Redactions and placeholders.** Placeholder symbols (blank lines, underlines, redaction markers, unexplained marks, unstated-number indicators) are never valid values and are never resolved into a guessed value. If an expression is made up only of a placeholder — with or without attached units or prepositions — the attribute is unstated (`null`, or `[]` for array fields). If it mixes a visible value with a placeholder, extract only the visible component.

### Rules for specific fields

5. **Array fields.** `dose`, `frequency` and `indication` hold one element per distinct value stated, in source order. Each element is verbatim under rule 1: the array never merges its elements into one string and never splits one expression across elements.

6. **`dosage_form` vs `route`.** Dosage form is the physical presentation of the drug; route is the path into the body. Any given expression belongs to one of the two, never to both — but a single line may state both, in either order.

### Field definitions

Top level:

- **medications_text**: the "Medications on Admission" section, verbatim, starting at the section heading itself (heading line included). Only pre-admission / home medications: if sub-sections for internal hospital status changes follow (such as "Inpatient Medications", "Hospital Medications" or "Discharge Medications"), truncate before they begin. `null` only when the note contains no such section at all; where the section exists, the value is the section text and is never `null`.

- **flag_is_medication_completed**: whether the note itself vouches for the list. `true` when the note states that the medication list is complete, accurate, verified or reconciled; `false` when it states that it is incomplete, unreliable or unverified; `null` only when the note makes no such statement at all. This statement is a sentence *about* the list rather than a medication entry, and typically sits directly under the section heading, before the entries begin — read it before extracting the entries.

- **medications**: one object per pre-admission or home medication mention. A medication administered at several times of day under a single mention remains one object; the varying doses and schedules are carried by the `dose` and `frequency` arrays. Do not extract medications under sub-headings for hospital care transitions, such as "Inpatient Medications" or "Discharge Medications". Never emit an object standing in for an absent medication: every object requires a `span_text` copied from the note.

- **span_text**: the medication mention as written. Its internal content is never altered — nothing inside is stripped, reordered, normalised or expanded, delimiters included; the sole permitted change is the newline substitution required in the structural rules above. Only trailing material is trimmed: trailing parenthetical context that maps to no attribute, trailing list punctuation, surrounding whitespace and stray artifact characters at the end. Preserve leading numbering when the source has it; never add numbering it does not have.

Attributes:

- **active_substance**: the chemical or generic name as written in the note. If the entry names only a brand, leave `null` — never supply the generic name from pharmacological knowledge. If more than one substance is named, extract all of them into that one string, preserving the separator used in the note: the value is the substance names as they appear, joined by the note's own separator, not a list of names. **Interleaved products:** when each substance is immediately followed by its own strength, so the names are not contiguous, join the names in source order with the separator that appears between them, omitting the intervening strengths and copying the separator's spacing exactly. This is the only case in which a value is assembled from non-contiguous text.

- **commercial_name**: brand or trade name, including descriptive over-the-counter product names and proprietary device delivery systems. A release modifier or strength designation that forms part of the registered brand name stays inside `commercial_name` and is not repeated elsewhere. `null` if only the active substance is mentioned.

- **dosage_form**: the physical presentation of the drug, plus infusion modes and release modifiers stated independently of a brand name. Always extract it when present, even if the same form word also appears inside the `quantity` string. Exception: a brand or proprietary device name belongs to `commercial_name` and is not repeated here, leaving `dosage_form` `null`.

- **dose**: array of measured amounts stating how much active substance the product contains — its strength or concentration — together with the rates at which it is administered. Units of mass, concentration, molar amount and biological potency belong here, as does device size or gauge. A strength stated with the active substance or medication name is always a `dose`, even when it describes the marketed product and even when the medication is administered as a discrete unit. Rates keep their time denominator, whether the numerator is an amount of substance or a volume: the exclusion of frequency refers to schedule markers, not rate denominators. What the patient physically takes is not a `dose`: counts of discrete units, and volumes stated without a rate, belong to `quantity`. Never include count units, route or schedule markers. An explicit statement that the strength is unknown or unverified yields `[]`. One element per distinct measured amount, in source order, however much internal structure each has: combination and multiphasic products keep the whole expression together, per-phase counts included, and are never split. **Interleaved products:** when each strength is stated immediately after its own substance, join them in source order into a **single element**, using the separator that appears between them and copying its spacing exactly.

- **quantity**: how much of the physical product the patient takes, written as a number followed by a **count unit** — a discrete, countable form, item or actuation in which the medication is dispensed or delivered — or a **unit of volume**. `quantity` answers how many physical units are administered; `dose` answers how much active substance they contain. A quantity carries no time denominator: an amount stated per unit of time is a rate, and the whole expression — denominator included — belongs to `dose`. Never strip a denominator, a unit or any other part of an expression to make it fit `quantity`; a value that does not fit `quantity` as written is not a quantity at all. A total stated without a rate is a quantity even when it accrues over an infusion rather than in a single intake. Units of mass, concentration, molar amount and biological potency belong to `dose`, even when the unit wording contains a count-related term. A number stated with no unit at all is a valid quantity where the note states the count that way, but only where it stands in the position of the amount taken: leading list numbering, clock times, figures inside schedule expressions, and any other number that does not state what is administered are never quantities. Never derive a `quantity` from a strength, and never include the schedule or frequency. `null` when redacted or not explicitly stated, and `null` when different quantities are given for different administration times, rather than selecting or combining them. The presence of `quantity` never suppresses `dose`: where both are stated, both are filled.

- **route**: the path by which the drug enters the body, exactly as it appears in the note, abbreviated or not. Not to be confused with `dosage_form`; a single line may state both. `null` when no route is stated.

- **frequency**: array of schedule expressions governing administration, each verbatim and without the dose amount or the route. Meal times, times of day and recurring daily events are schedule information and belong here, whether written inline or in parentheses attached to a dose. One element per distinct schedule stated, in source order.

- **duration**: the length of the treatment period, exactly as written. `null` if not stated.

- **indication**: array of clinical reasons or triggering conditions for administering the drug — the "why". Each element is copied literally under rule 1, severity qualifiers included and unchanged. One element per distinct reason stated.

- **administration_instructions**: free-text directions constraining how or under what conditions the drug is given — hold parameters, intake conditions, titration rules, application sites. An indication triggers administration; an instruction constrains it. Exclude trailing parenthetical context that maps to no attribute.