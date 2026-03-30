"""Signal trace inspector — step-by-step pipeline inspection.

Public API:
    trace_source_item(source_item_id, db) -> dict
    fetch_samples(source_type, count, db) -> list[dict]
"""

from app.services.trace.tracer import fetch_samples, trace_source_item

__all__ = ["trace_source_item", "fetch_samples"]
