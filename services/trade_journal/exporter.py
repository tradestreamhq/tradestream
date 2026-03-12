"""Export trade journal entries to CSV and JSON formats."""

import csv
import io
import json
from typing import Any

from services.trade_journal.models import JournalEntry

CSV_COLUMNS = [
    "id",
    "trade_id",
    "strategy",
    "symbol",
    "side",
    "entry_price",
    "entry_rationale",
    "exit_price",
    "exit_rationale",
    "outcome",
    "pnl",
    "lessons",
    "tags",
    "created_at",
    "closed_at",
]


def to_csv(entries: list[JournalEntry]) -> str:
    """Export journal entries to a CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()

    for entry in entries:
        row = entry.to_dict()
        # Flatten tags list to comma-separated string
        row["tags"] = ",".join(row.get("tags", []))
        # Remove signals_at_entry (complex nested dict, not suitable for CSV)
        row.pop("signals_at_entry", None)
        writer.writerow(row)

    return output.getvalue()


def to_json(entries: list[JournalEntry], indent: int = 2) -> str:
    """Export journal entries to a JSON string."""
    return json.dumps(
        [entry.to_dict() for entry in entries],
        indent=indent,
    )
