"""Central project paths used by loaders, runners, and tests."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOGGING_DIR = PROJECT_ROOT / "logging"
DOCS_DIR = PROJECT_ROOT / "docs"

