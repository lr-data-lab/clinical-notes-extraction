"""Centralised configuration loaded from .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")
#DATA_DIR = _REPO_ROOT / "data"

GCP_BILLING_PROJECT = os.environ["GCP_BILLING_PROJECT"]


QUERIES_DIR = Path(__file__).resolve().parents[2] / "queries/mimic_iv"
QUERY_FILE_NAME = "discharge_notes.sql"
