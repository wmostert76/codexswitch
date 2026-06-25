"""Shared fixtures for CodexSwitch tests."""
import sys
from pathlib import Path

# Make bin/ importable
BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
sys.path.insert(0, str(BIN_DIR))
