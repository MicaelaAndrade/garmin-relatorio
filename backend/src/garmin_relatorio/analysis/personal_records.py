"""Lista PRs relevantes do Garmin."""
from __future__ import annotations

from ..db import connect

# Ordem de exibicao: PRs mais relevantes pra triathlon vem primeiro
RELEVANT_TYPES = [
    "Best 1km Run",
    "Best 1mile Run",
    "Best 5km Run",
    "Best 10km Run",
    "Farthest Run",
    "Best 100m Pool Swim",
    "Best 400m Pool Swim",
    "Best 750m Pool Swim",
    "Best 1000m Pool Swim",
    "Longest Pool Swim",
    "Best 40km Cycle",
    "Farthest Cycle",
    "Max Elevation Gain",
    "Most Steps in a Day",
    "Most Steps in a Week",
    "Most Steps in a Month",
    "Current Goal Streak",
    "Longest Goal Streak",
]


def list_prs() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT pr_id, record_type, value, achieved_at, is_current
            FROM personal_records
            WHERE is_current = 1
            ORDER BY record_type
            """
        ).fetchall()
    out = [dict(r) for r in rows]

    # ordena por relevancia (RELEVANT_TYPES first), depois alfabetico
    def sort_key(pr):
        try:
            return (RELEVANT_TYPES.index(pr["record_type"]), pr["record_type"])
        except ValueError:
            return (999, pr["record_type"])

    out.sort(key=sort_key)
    return out
