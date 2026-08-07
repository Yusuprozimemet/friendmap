"""Recency buckets, shared by the map legend and the ranking.

Kept in one place so "fresh" can't come to mean 7 days in one and 14 in the
other.
"""
from __future__ import annotations

FRESH_DAYS = 7
RECENT_DAYS = 30


def recency_weight(days_ago: int) -> float:
    """1.0 for this week, 0.5 for this month, 0 beyond."""
    if days_ago <= FRESH_DAYS:
        return 1.0
    if days_ago <= RECENT_DAYS:
        return 0.5
    return 0.0
