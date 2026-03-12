"""Feed processor that aggregates sentiment records per symbol."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from services.sentiment_api.analyzer import analyze_text
from services.sentiment_api.models import AggregatedSentiment, SentimentRecord


class SentimentStore:
    """In-memory store for sentiment records with per-symbol aggregation."""

    def __init__(self):
        self._records: Dict[str, List[SentimentRecord]] = defaultdict(list)

    def add_record(self, record: SentimentRecord) -> None:
        self._records[record.symbol].append(record)

    def ingest_text(
        self,
        text: str,
        symbol: str,
        source: str,
        timestamp: Optional[datetime] = None,
    ) -> SentimentRecord:
        """Analyze text and store the resulting record."""
        record = analyze_text(text, symbol, source, timestamp)
        self.add_record(record)
        return record

    def get_records(
        self,
        symbol: str,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
    ) -> List[SentimentRecord]:
        """Get sentiment records for a symbol within an optional time range."""
        records = self._records.get(symbol, [])
        if from_time:
            records = [r for r in records if r.timestamp >= from_time]
        if to_time:
            records = [r for r in records if r.timestamp <= to_time]
        return sorted(records, key=lambda r: r.timestamp, reverse=True)

    def get_aggregated(
        self,
        symbol: str,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
    ) -> Optional[AggregatedSentiment]:
        """Compute rolling sentiment aggregation for a symbol."""
        records = self.get_records(symbol, from_time, to_time)
        if not records:
            return None

        scores = [r.score for r in records]
        avg_score = sum(scores) / len(scores)
        sources = sorted(set(r.source for r in records))

        earliest = min(r.timestamp for r in records)
        latest = max(r.timestamp for r in records)

        # Velocity: change in sentiment per hour
        velocity = 0.0
        duration_hours = (latest - earliest).total_seconds() / 3600
        if duration_hours > 0 and len(records) >= 2:
            # Split into first half and second half
            mid = len(records) // 2
            # Records are sorted newest-first
            recent_avg = sum(r.score for r in records[:mid]) / mid
            older_avg = sum(r.score for r in records[mid:]) / (len(records) - mid)
            velocity = (recent_avg - older_avg) / duration_hours

        return AggregatedSentiment(
            symbol=symbol,
            average_score=avg_score,
            record_count=len(records),
            velocity=velocity,
            from_time=earliest,
            to_time=latest,
            sources=sources,
        )
