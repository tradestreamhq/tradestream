"""Output formatters for export endpoints (CSV and JSON)."""

import csv
import io
from typing import Any, Dict, List, Sequence

from fastapi.responses import JSONResponse, StreamingResponse


def to_csv_response(
    rows: Sequence[Dict[str, Any]],
    filename: str,
) -> StreamingResponse:
    """Convert a list of dicts to a CSV streaming response."""
    if not rows:
        return StreamingResponse(
            iter([""]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _serialize_value(v) for k, v in row.items()})

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def to_json_export_response(
    rows: Sequence[Dict[str, Any]],
    total: int,
    limit: int,
    offset: int,
) -> JSONResponse:
    """Return export data as JSON with pagination metadata."""
    return JSONResponse(
        content={
            "data": list(rows),
            "meta": {"total": total, "limit": limit, "offset": offset},
        }
    )


def _serialize_value(value: Any) -> str:
    """Serialize a value for CSV output."""
    if value is None:
        return ""
    if isinstance(value, dict):
        import json

        return json.dumps(value)
    if isinstance(value, list):
        import json

        return json.dumps(value)
    return str(value)
