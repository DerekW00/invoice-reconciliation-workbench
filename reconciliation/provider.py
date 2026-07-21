"""No network adapter. Files are frozen scripted responses, never financial authority."""

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "provider"


def explain(facts: list[dict[str, Any]], mode: str = "normal") -> dict[str, Any]:
    if len(facts) > 100 or len(json.dumps(facts).encode()) > 32768:
        raise ValueError("Explanation input cap exceeded")
    if mode not in {"normal", "invalid_ids", "malformed", "failure"}:
        raise ValueError("Unknown fixture")
    response = json.loads((FIXTURES / f"{mode}.json").read_text())
    if "error" in response:
        raise ValueError(response["error"])
    ids = [f["id"] for f in facts]
    if response.get("fact_ids") == "$input":
        response["fact_ids"] = ids
    if set(response) != {"source", "text", "fact_ids", "usage"} or response["fact_ids"] != ids:
        raise ValueError("Explanation must cite exactly the supplied fact IDs")
    if not isinstance(response["text"], str) or len(response["text"]) > 2000:
        raise ValueError("Invalid explanation text")
    return response
