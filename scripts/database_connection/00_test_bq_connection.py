"""Smoke test: authenticate to BigQuery and verify MIMIC-IV access."""
import logging

from clinical_notes_extraction.bq import get_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    client = get_client()
    logger.info(f"Authenticated to project: {client.project}")

    query = """
    SELECT COUNT(*) AS n_notes
    FROM `physionet-data.mimiciv_note.discharge`
    """
    result = client.query(query).result()
    for row in result:
        logger.info(f"Total discharge notes accessible: {row.n_notes:,}")


if __name__ == "__main__":
    main()