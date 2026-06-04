"""BigQuery helpers shared across scripts."""
from google.cloud import bigquery

from clinical_notes_extraction.config import GCP_BILLING_PROJECT


def get_client() -> bigquery.Client:
    """Return a BigQuery client billed to GCP PROJECT."""
    return bigquery.Client(project=GCP_BILLING_PROJECT)