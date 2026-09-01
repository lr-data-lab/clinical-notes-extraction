# eda.py
import pandas as pd
import re
import matplotlib.pyplot as plt
import seaborn as sns

# ============================================================
# Age & demographics
# ============================================================

def classify_age(age) -> str | None:
    """Classify a patient's age into a predefined age group bucket.
    
    Args:
        age: Numeric age value (can be NaN).
    
    Returns:
        Age group string (e.g. '[20, 39]'), or None if age is missing.
    """
    if pd.isna(age):
        return None
    elif 10 <= age <= 19:
        return '[10, 19]'
    elif 20 <= age <= 39:
        return '[20, 39]'
    elif 40 <= age <= 59:
        return '[40, 59]'
    elif 60 <= age <= 79:
        return '[60, 79]'
    else:
        return '[80+]'



# ============================================================
# Outlier detection
# ============================================================

def iqr_outliers(s: pd.Series) -> tuple[int, float, float]:
    """Calculate IQR bounds and count outliers in a pandas Series.

    Args:
        s: Numeric pandas Series (NaNs should be dropped before passing).

    Returns:
        Tuple of (number of outliers, lower bound, upper bound).
    """
    # Get the 25th (Q1) and 75th (Q3) percentiles
    q1, q3 = s.quantile([0.25, 0.75])

    # Interquartile range: the middle 50% of the data
    iqr = q3 - q1

    # Standard 1.5 * IQR rule to define outlier bounds
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr

    # Boolean mask of values outside the bounds; .sum() counts True values
    return ((s < lo) | (s > hi)).sum(), lo, hi


# ============================================================
# Text cleaning
# ============================================================

# Precompile regex patterns once at module level so they aren't recompiled
# on every call. This matters when applying clean_note() across a large
# DataFrame (e.g. all MIMIC-IV discharge notes).

# A "garbage" line is one made up ONLY of noise characters: . - / X ? n _
# re.IGNORECASE means 'x'/'X' and 'n'/'N' are both caught.
# '_' is included to catch MIMIC-IV de-identification markers (e.g. '___').
_GARBAGE_PATTERN = re.compile(r"^[.\-/X?n_]+$", re.IGNORECASE)

_MULTISPACE_PATTERN = re.compile(r"[ \t]+")    # multiple spaces/tabs
_EXTRA_NEWLINES_PATTERN = re.compile(r"\n{3,}") # 3+ consecutive newlines

# Values that, after cleaning, should be treated as "no note"
_EMPTY_VALUES = {"", "na", "n/a", "none", "nan", "null", "unknown"}


def clean_note(text) -> str | None:
    """ 
    Cleans a single text note and returns the processed version, or `None` if the result is not usable.

    1. Returns `None` if the input is not a `str` (NaN, numbers, `None`).
    2. Normalizes line endings (`\r\n` and `\r` → `\n`).
    3. Strips whitespace from each line.
    4. Removes lines made up **only** of noise characters — `. - / X ? n _`
    (case-insensitive).
    5. Collapses runs of spaces/tabs, caps paragraph breaks at a single blank
    line, and strips the result.
    6. Returns `None` if the result is empty or matches a null-equivalent
    sentinel (`""`, `na`, `n/a`, `none`, `nan`, `null`, `unknown`);
    otherwise returns the cleaned text.
    """

    # 1. Fail-safe for non-string inputs (NaN, numbers, None, etc.)
    if not isinstance(text, str):
        return None

    # 2. Standardize line endings to '\n'
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Trim spaces from each line and drop pure-noise lines in one pass
    lines = [
        stripped
        for line in text.split("\n")
        if not _GARBAGE_PATTERN.match(stripped := line.strip())
    ]

    # 4. Rejoin and normalize overall spacing
    text = "\n".join(lines)
    text = _MULTISPACE_PATTERN.sub(" ", text)         # collapse spaces/tabs
    text = _EXTRA_NEWLINES_PATTERN.sub("\n\n", text)  # cap paragraph breaks
    text = text.strip()

    # 5. Final check: treat empty / 'na' results as missing
    if text.lower() in _EMPTY_VALUES:
        return None

    return text


def clean_and_drop_na_values(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Applies `clean_note` to an entire DataFrame column.

    - Creates a `<column>_cleaned` column with the cleaning result.
    - Drops rows where the cleaned note is `None`.
    - Returns a **copy** of the DataFrame; the caller's object is not mutated.

    **Notes**
    - The noise pattern **includes** `_`, so lines consisting only of MIMIC-IV
    de-identification markers (`___`) are removed. Markers embedded inside a
    line of real content are preserved — a redacted dose must remain visible
    to the model as missing information, not be silently deleted.
    - The regex patterns are compiled once at module level, since the function
    is applied across the full set of discharge notes.
    """
    df = df.copy()
    new_col = f"{column}_cleaned"

    # Apply clean_note to every value in the column
    df[new_col] = df[column].apply(clean_note)

    # Drop rows where the cleaned note became None (invalid or empty)
    df = df.dropna(subset=[new_col])

    return df


# ============================================================
# Plots
# ============================================================

def histogram_boxplot(df: pd.DataFrame, column: str, bins: int) -> None:
    """Plot a histogram and boxplot side by side for a single column.

    Args:
        df: DataFrame containing the column to plot.
        column: Name of the column to visualise.
        bins: Number of bins for the histogram.
    """
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.2))

    # Left: histogram of non-null values
    df[column].dropna().hist(bins=bins, ax=ax[0])
    ax[0].set_title(f"{column} — Histogram")

    # Right: boxplot to visualise spread and outliers
    sns.boxplot(x=df[column], ax=ax[1])
    ax[1].set_title(f"{column} — Boxplot")

    plt.tight_layout()
    plt.show()


# ============================================================
# Deduplication
# ============================================================

def get_notes_with_duplicate_admission_meds(notes_df: pd.DataFrame, patient_id: int) -> pd.DataFrame:
    """Return a patient's notes whose cleaned admission meds match at least
    one other note from the same patient.

    Empty or NaN med values are ignored so they are not flagged as duplicates.
    Assumes `meds_on_admission_cleaned` is a string column and `note_id`
    is unique per note.

    Args:
        notes_df: DataFrame containing all notes.
        patient_id: The subject_id of the patient to check.

    Returns:
        DataFrame with note_id and meds_on_admission_cleaned for duplicate notes.
    """
    # Filter to this patient's notes only
    patient_df = notes_df[notes_df['subject_id'] == patient_id]

    meds = patient_df['meds_on_admission_cleaned']

    # Exclude empty or NaN values — they are not meaningful duplicates
    has_meds = meds.notna() & (meds.str.strip() != '')

    # keep=False flags ALL occurrences of a duplicated value, not just the second
    duplicates = patient_df[has_meds & meds.duplicated(keep=False)]

    return duplicates[['note_id', 'meds_on_admission_cleaned']]



# ============================================================
# String formatting
# ============================================================

def capitalize_first_char(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Return a new DataFrame where the FIRST character of `column` is
    upper-cased and every other character is left exactly as-is.

    Operates on position 0 literally, not on the first *letter*: if the
    string starts with a space, digit or symbol, that character is passed
    through unchanged (upper-casing it is a no-op) and the rest is untouched.
        "started on IV"  -> "Started on IV"
        "5mg aspirin"    -> "5mg aspirin"   (digit unchanged)
        " iv fluids"     -> " iv fluids"    (leading space unchanged)

    The rest of the string is deliberately NOT lower-cased: in clinical text
    some words carry meaning precisely through their upper-case form (e.g.
    abbreviations and acronyms such as "IV", "PRN", "PO", "COPD"), and
    forcing them to lower-case would discard that information.

    NaN/None values are left untouched; the input is not mutated.

    Args:
        df: DataFrame containing the column to format.
        column: Name of the column to apply the transformation to.

    Returns:
        Copy of the DataFrame with the first character of the column upper-cased.
    """
    df = df.copy()

    # Upper-case only the first character; keep the remainder verbatim so that
    # meaningful upper-case tokens (IV, PRN, COPD, ...) are preserved.
    s = df[column].astype('string')
    df[column] = s.str[:1].str.upper() + s.str[1:]

    return df