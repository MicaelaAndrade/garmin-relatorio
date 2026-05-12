"""Cobertura de dados por fonte: pra cada origem (Garmin, Zepp, Strava etc),
quantos registros, range temporal, dias desde a ultima atualizacao e status
(fresco / ok / desatualizado / antigo).

Util pra usuaria saber quando precisa exportar de novo o GDPR ou o Zepp Life.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..db import connect


# Thresholds em dias pra cada categoria de status
THRESHOLDS = {
    "fresh": 7,        # < 7 dias = fresco
    "ok": 30,          # < 30 dias = OK
    "stale": 90,       # < 90 dias = desatualizado
    # > 90 = antigo
}


def _status_for_days(days: int | None) -> tuple[str, str]:
    if days is None:
        return "unknown", "—"
    if days <= THRESHOLDS["fresh"]:
        return "fresh", "atualizado"
    if days <= THRESHOLDS["ok"]:
        return "ok", "OK"
    if days <= THRESHOLDS["stale"]:
        return "stale", "atualize logo"
    return "old", "muito antigo"


def _days_since(iso_date: str | None) -> int | None:
    if not iso_date:
        return None
    try:
        # Aceita 'YYYY-MM-DD' OU ISO 8601 completo
        d = datetime.fromisoformat(iso_date[:19].replace("Z", "+00:00")) if "T" in iso_date else datetime.fromisoformat(iso_date[:10])
    except ValueError:
        return None
    today = datetime.now(d.tzinfo) if d.tzinfo else datetime.now()
    return max(0, (today.date() - d.date()).days)


def _suggest_command(source_kind: str, days_since: int | None, latest: str | None) -> str | None:
    """Comando sugerido pra atualizar a fonte (None quando esta fresca)."""
    if days_since is None or days_since <= THRESHOLDS["fresh"]:
        return None
    commands = {
        "garmin_activities": "uv run garmin-relatorio ingest-garmin --days 30",
        "garmin_sleep": "uv run garmin-relatorio ingest-garmin --what sleep",
        "garmin_daily": "uv run garmin-relatorio ingest-garmin --what daily",
        "garmin_export": "uv run garmin-relatorio ingest-export  # novo export GDPR",
        "zepp_body": "uv run garmin-relatorio ingest-zepp /path/to/new-export",
        "strava": "uv run garmin-relatorio ingest-strava --days 30",
    }
    return commands.get(source_kind)


def data_sources_status() -> dict[str, Any]:
    """Lista cobertura por fonte ordenada pela mais antiga primeiro (mais urgente)."""
    today = date.today()
    sources: list[dict[str, Any]] = []

    with connect() as conn:
        # Garmin activities (live + GDPR consolidados no source='garmin')
        row = conn.execute(
            """
            SELECT MIN(date(started_at)) AS first, MAX(date(started_at)) AS last, COUNT(*) AS n
            FROM activities WHERE source='garmin'
            """
        ).fetchone()
        if row and row["n"]:
            days = _days_since(row["last"])
            status, label = _status_for_days(days)
            sources.append({
                "kind": "garmin_activities",
                "label": "Garmin — atividades",
                "icon": "🏃",
                "first": row["first"],
                "last": row["last"],
                "count": row["n"],
                "days_since": days,
                "status": status,
                "status_label": label,
                "suggestion": _suggest_command("garmin_activities", days, row["last"]),
            })

        # Strava (se houver atividades importadas)
        row = conn.execute(
            """
            SELECT MIN(date(started_at)) AS first, MAX(date(started_at)) AS last, COUNT(*) AS n
            FROM activities WHERE source='strava'
            """
        ).fetchone()
        if row and row["n"]:
            days = _days_since(row["last"])
            status, label = _status_for_days(days)
            sources.append({
                "kind": "strava",
                "label": "Strava — atividades",
                "icon": "🟧",
                "first": row["first"],
                "last": row["last"],
                "count": row["n"],
                "days_since": days,
                "status": status,
                "status_label": label,
                "suggestion": _suggest_command("strava", days, row["last"]),
            })

        # Sono
        row = conn.execute(
            "SELECT MIN(date) AS first, MAX(date) AS last, COUNT(*) AS n FROM sleep"
        ).fetchone()
        if row and row["n"]:
            days = _days_since(row["last"])
            status, label = _status_for_days(days)
            sources.append({
                "kind": "garmin_sleep",
                "label": "Garmin — sono",
                "icon": "😴",
                "first": row["first"],
                "last": row["last"],
                "count": row["n"],
                "days_since": days,
                "status": status,
                "status_label": label,
                "suggestion": _suggest_command("garmin_sleep", days, row["last"]),
            })

        # Daily metrics (HRV, RHR, stress, body battery)
        row = conn.execute(
            "SELECT MIN(date) AS first, MAX(date) AS last, COUNT(*) AS n FROM daily_metrics"
        ).fetchone()
        if row and row["n"]:
            days = _days_since(row["last"])
            status, label = _status_for_days(days)
            sources.append({
                "kind": "garmin_daily",
                "label": "Garmin — métricas diárias",
                "icon": "❤️",
                "first": row["first"],
                "last": row["last"],
                "count": row["n"],
                "days_since": days,
                "status": status,
                "status_label": label,
                "suggestion": _suggest_command("garmin_daily", days, row["last"]),
            })

        # Composicao corporal (Zepp ou similar)
        rows = conn.execute(
            """
            SELECT source, MIN(date(measured_at)) AS first, MAX(date(measured_at)) AS last, COUNT(*) AS n
            FROM body_composition GROUP BY source
            """
        ).fetchall()
        for r in rows:
            days = _days_since(r["last"])
            status, label = _status_for_days(days)
            kind = f"{r['source']}_body" if r["source"] == "zepp" else f"{r['source']}_body"
            sources.append({
                "kind": kind,
                "label": (
                    "Zepp Life — bioimpedância"
                    if r["source"] == "zepp"
                    else f"{r['source'].capitalize()} — bioimpedância"
                ),
                "icon": "⚖️",
                "first": r["first"],
                "last": r["last"],
                "count": r["n"],
                "days_since": days,
                "status": status,
                "status_label": label,
                "suggestion": _suggest_command(kind, days, r["last"]),
            })

        # VO2max
        row = conn.execute(
            "SELECT MIN(date) AS first, MAX(date) AS last, COUNT(*) AS n FROM vo2max"
        ).fetchone()
        if row and row["n"]:
            days = _days_since(row["last"])
            status, label = _status_for_days(days)
            sources.append({
                "kind": "garmin_export",
                "label": "Garmin — VO2max / predições",
                "icon": "📈",
                "first": row["first"],
                "last": row["last"],
                "count": row["n"],
                "days_since": days,
                "status": status,
                "status_label": label,
                "suggestion": _suggest_command("garmin_export", days, row["last"]),
            })

    # Ordena por status: old > stale > ok > fresh > unknown (mais urgentes primeiro)
    priority = {"old": 0, "stale": 1, "ok": 2, "fresh": 3, "unknown": 4}
    sources.sort(key=lambda s: (priority.get(s["status"], 5), -(s["days_since"] or 0)))

    # Coberturas globais
    all_firsts = [s["first"] for s in sources if s.get("first")]
    all_lasts = [s["last"] for s in sources if s.get("last")]

    return {
        "available": bool(sources),
        "today": today.isoformat(),
        "coverage": {
            "first": min(all_firsts) if all_firsts else None,
            "last": max(all_lasts) if all_lasts else None,
        },
        "sources": sources,
        "needs_attention": any(s["status"] in ("stale", "old") for s in sources),
    }
