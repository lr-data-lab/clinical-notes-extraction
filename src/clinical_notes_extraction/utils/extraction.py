import re

import pandas as pd


def _extract_section(text: str, header: str) -> str | None:
    """Return the body of one section from a single note, or None if absent.

    Args:
        text: The full note as a single string.
        header: The section title to find, e.g. "Discharge Medications".

    Returns:
        Section body as a stripped string, or None if the section is not found.
    """
    if not isinstance(text, str):  # guard against missing/empty notes
        return None

    # Match the header, capture everything after it (non-greedy),
    # and stop at the next section title or end of note.
    pattern = (
        re.escape(header) + r"\s*:?\s*\n?"
        r"(.*?)"
        r"(?=\n[ \t]*\n?[A-Z][A-Za-z /]+:\s*\n|\Z)"
    )
    match = re.search(pattern, text, re.DOTALL)  # DOTALL allows multi-line matching
    return match.group(1).strip() if match else None


def add_medication_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add admission and discharge medication section columns to the DataFrame.

    Args:
        df: DataFrame containing a 'text' column with full clinical notes.

    Returns:
        Copy of the DataFrame with two new columns:
        - 'meds_on_admission': body of the "Medications on Admission" section
        - 'meds_on_discharge': body of the "Discharge Medications" section
    """
    out = df.copy()

    out["meds_on_admission"] = out["text"].apply(
        lambda note: _extract_section(note, "Medications on Admission")
    )
    out["meds_on_discharge"] = out["text"].apply(
        lambda note: _extract_section(note, "Discharge Medications")
    )

    # Coverage: fraction of notes where each section was found
    print(f"Admission meds found in {100 * out['meds_on_admission'].notna().mean():.1f}% of notes")
    print(f"Discharge meds found in {100 * out['meds_on_discharge'].notna().mean():.1f}% of notes")
    return out