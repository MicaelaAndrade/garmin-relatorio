"""Rotinas de fortalecimento importadas do MFit Personal (ou outro app).

Expoe:
- strength_dashboard(): retorna rotina de hoje (se houver) + todas as rotinas
- strength_routine(routine_id): detalhe de uma rotina
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ..db import connect


DAY_LABELS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _routine_row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "order_idx": row["order_idx"],
        "weekday": row["weekday"],
        "weekday_label": DAY_LABELS[row["weekday"]] if row["weekday"] is not None else None,
        "routine_label": row["routine_label"],
        "fitness_level": row["fitness_level"],
        "source": row["source"],
        "source_file": row["source_file"],
    }


def _list_exercises(conn, routine_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM strength_exercises WHERE routine_id = ? ORDER BY order_idx",
        (routine_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "order_idx": r["order_idx"],
            "name": r["name"],
            "sets": r["sets"],
            "load_kg": r["load_kg"],
            "load_text": r["load_text"],
            "rest_s": r["rest_s"],
            "rest_text": r["rest_text"],
            "instructions": r["instructions"],
            "is_warmup": (r["name"] or "").lower().startswith("alongamento"),
        }
        for r in rows
    ]


def strength_dashboard() -> dict[str, Any]:
    today_weekday = date.today().weekday()
    with connect() as conn:
        all_routines = conn.execute(
            "SELECT * FROM strength_routines ORDER BY order_idx"
        ).fetchall()
        today_routine_row = next(
            (r for r in all_routines if r["weekday"] == today_weekday),
            None,
        )
        today_routine = None
        if today_routine_row:
            today_routine = {
                **_routine_row_to_dict(today_routine_row),
                "exercises": _list_exercises(conn, today_routine_row["id"]),
            }

        # Resumo dos exercicios e' caro: so' retornamos exercises se today_routine
        routines_summary = [_routine_row_to_dict(r) for r in all_routines]
        for s in routines_summary:
            s["exercise_count"] = conn.execute(
                "SELECT COUNT(*) FROM strength_exercises WHERE routine_id = ?",
                (s["id"],),
            ).fetchone()[0]

    return {
        "today": today_routine,
        "today_weekday_label": DAY_LABELS[today_weekday],
        "routines": routines_summary,
        "available": len(routines_summary) > 0,
    }


def strength_routine(routine_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM strength_routines WHERE id = ?",
            (routine_id,),
        ).fetchone()
        if not row:
            return None
        return {
            **_routine_row_to_dict(row),
            "exercises": _list_exercises(conn, row["id"]),
        }
