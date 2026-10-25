"""Smoke tests for AI Email Classifier & WhatsApp Alerter."""

import subprocess
import sys


def test_cli_help():
    """Verify that CLI --help executes with exit code 0 and outputs expected description."""
    result = subprocess.run([sys.executable, "main.py", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "email monitor" in result.stdout.lower() or "email classifier" in result.stdout.lower()
