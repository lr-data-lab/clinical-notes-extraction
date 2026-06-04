"""Shared helpers: query loading and logging setup."""
import logging
from pathlib import Path

from clinical_notes_extraction.config import QUERIES_DIR


def load_query(filename: str, **params) -> str:
    """Read queries/<filename> and substitute {placeholders}."""
    text = (QUERIES_DIR / filename).read_text(encoding="utf-8")
    return text.format(**params) if params else text


def configure_logging(log_path: Path) -> None:
    """Log to stdout + log_path (overwrites each run)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s | %(levelname)s | %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, force=True)
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter(fmt))
    logging.getLogger().addHandler(fh)