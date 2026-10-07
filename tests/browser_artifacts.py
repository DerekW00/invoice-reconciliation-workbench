"""Writable browser artifacts independent of the execution user's checkout."""

import os
import tempfile
from pathlib import Path


def evidence_directory() -> Path:
    configured = os.environ.get("BROWSER_EVIDENCE_DIR")
    path = (
        Path(configured).expanduser().resolve()
        if configured
        else Path(tempfile.mkdtemp(prefix="invoice_recon-browser-"))
    )
    path.mkdir(parents=True, exist_ok=True)
    return path
