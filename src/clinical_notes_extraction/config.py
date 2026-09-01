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
    "medgemma:27b": 20.0,
    "gemma3:27b":   20.0,
    "llama4:scout": 71.0,
}


# Written by the file 3_check_server_capabilities; consumed by download_models and run_extraction.
CONFIG_DIR = PROJECT_ROOT / "config"
RUNNABLE_MODELS_FILE = CONFIG_DIR / "runnable_models.json"