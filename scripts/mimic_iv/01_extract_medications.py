"""Extract admission/discharge medication sections from MIMIC-IV discharge notes.

Reads the notes directly from BigQuery (no CSV), pulls out the two medication
sections with regex, and writes the result to DATA_DIR.

Note: this step does NOT use an LLM. The extraction is plain text-matching and
runs entirely on this machine; the only data that moves is the BigQuery read.
"""
import logging
import re

import pandas as pd
from google.cloud import bigquery

from clinical_notes_extraction.config import DATA_DIR, GCP_BILLING_PROJECT, QUERY_FILE_NAME
from clinical_notes_extraction.utils import configure_logging, load_query

logger = logging.getLogger(__name__)


def fetch_data(query_file) -> pd.DataFrame:
    """Read the discharge notes directly from BigQuery into a DataFrame."""
    client = bigquery.Client(project=GCP_BILLING_PROJECT)
    sql = load_query(query_file)
    logger.info("Querying BigQuery (billing project: %s)", GCP_BILLING_PROJECT)
    df = client.query(sql).to_dataframe(progress_bar_type="tqdm")
    logger.info("Fetched %d notes", len(df))
    return df

def extract_section(text, header):
    """Return the body of one section from a single note, or None if absent.

    'text'   = the full note (one string)
    'header' = the section title to find, e.g. "Discharge Medications"
    """
    if not isinstance(text, str):  # some notes may be empty / missing
        return None

    # Find the title, keep everything after it (.*?), and stop at the next
    # section title or the end of the note.
    pattern = (
        re.escape(header) + r"\s*:?\s*\n?"
        r"(.*?)"
        r"(?=\n[ \t]*\n?[A-Z][A-Za-z /]+:\s*\n|\Z)"
    )
    match = re.search(pattern, text, re.DOTALL)  # DOTALL = allow multi-line
    return match.group(1).strip() if match else None


def add_medication_sections(df: pd.DataFrame) -> pd.DataFrame:
    """Add the two medication-section columns to a copy of the DataFrame."""
    out = df.copy()

    out["meds_on_admission"] = out["text"].apply(
        lambda note: extract_section(note, "Medications on Admission")
    )
    out["meds_on_discharge"] = out["text"].apply(
        lambda note: extract_section(note, "Discharge Medications")
    )

    # Coverage: what fraction of notes did we actually find each section in?
    logger.info("Admission meds found in %.1f%% of notes", 100 * out["meds_on_admission"].notna().mean())
    logger.info("Discharge meds found in %.1f%% of notes", 100 * out["meds_on_discharge"].notna().mean())
    return out


def main() -> None:
    configure_logging(DATA_DIR / "logs" / "extract_medications.log")

    df = fetch_data(QUERY_FILE_NAME)
    df = add_medication_sections(df)

    out_path = DATA_DIR / "discharge_notes_with_meds.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)  # swap for .to_csv if pyarrow isn't installed
    logger.info("Wrote %d rows to %s", len(df), out_path)


if __name__ == "__main__":
    main()