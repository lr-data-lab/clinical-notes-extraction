import pandas as pd
from google.cloud import bigquery

from clinical_notes_extraction.config import GCP_BILLING_PROJECT, QUERIES_DIR


def load_query(filename: str, **params) -> str:
    """Read queries/<filename> and substitute {placeholders} if provided.

    Args:
        filename: Name of the .sql file inside the queries/ directory.
        **params: Optional key-value pairs to substitute into the query.

    Returns:
        SQL query as a string, ready to send to BigQuery.
    """
    text = (QUERIES_DIR / filename).read_text(encoding="utf-8")
    return text.format(**params) if params else text


def fetch_data(query_file: str) -> pd.DataFrame:
    """Fetch query results from BigQuery into a DataFrame.

    Args:
        query_file: Name of the .sql file inside the queries/ directory.

    Returns:
        DataFrame with the query results.
    """
    client = bigquery.Client(project=GCP_BILLING_PROJECT)
    sql = load_query(query_file)
    print(f"Querying BigQuery (billing project: {GCP_BILLING_PROJECT})")
    df = client.query(sql).to_dataframe(progress_bar_type="tqdm")
    print(f"Fetched {len(df):,} rows")
    return df