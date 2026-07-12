"""Centralised configuration loaded from .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

GCP_BILLING_PROJECT = os.environ["GCP_BILLING_PROJECT"]


QUERIES_DIR = Path(__file__).resolve().parents[2] / "queries/mimic_iv"
QUERY_FILE_NAME = "discharge_notes.sql"


## LLM candidate models
CANDIDATE_MODELS = {
    "medgemma:27b": 19.0,     # ~17 GB weights + overhead 
    "llama3.1:70b": 42.0,     # ~40 GB weights + overhead
    "deepseek-r1:70b": 43.0,  # ~43 GB weights + overhead
}


# Written by the file 3_check_server_capabilities; consumed by download_models and run_extraction.
CONFIG_DIR = PROJECT_ROOT / "config"
RUNNABLE_MODELS_FILE = CONFIG_DIR / "runnable_models.json"