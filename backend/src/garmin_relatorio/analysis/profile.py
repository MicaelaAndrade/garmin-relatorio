"""Perfil do usuário + biometria.

Combina user_profile + biometrics em um snapshot atual + timeline.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ..db import connect


def _calc_age(birth_date_str: str | None) -> int | None:
    if not birth_date_str:
        return None
    try:
        bd = date.fromisoformat(birth_date_str)
    except ValueError:
        return None
    today = date.today()
    years = today.year - bd.year
    if (today.month, today.day) < (bd.month, bd.day):
        years -= 1
    return years


def _latest(conn, column: str) -> tuple[str | None, float | None]:
    row = conn.execute(
        f"SELECT date, {column} FROM biometrics WHERE {column} IS NOT NULL ORDER BY date DESC LIMIT 1",
    ).fetchone()
    if not row:
        return None, None
    return row["date"], row[column]


def _first(conn, column: str) -> tuple[str | None, float | None]:
    row = conn.execute(
        f"SELECT date, {column} FROM biometrics WHERE {column} IS NOT NULL ORDER BY date ASC LIMIT 1",
    ).fetchone()
    if not row:
        return None, None
    return row["date"], row[column]


def profile_dashboard() -> dict[str, Any]:
    with connect() as conn:
        prof = conn.execute("SELECT * FROM user_profile LIMIT 1").fetchone()
        prof_dict = dict(prof) if prof else None

        weight_date, weight_g = _latest(conn, "weight_g")
        weight_first_date, weight_first_g = _first(conn, "weight_g")
        height_date, height_cm = _latest(conn, "height_cm")
        vo2_date, vo2 = _latest(conn, "vo2max_running")
        vo2_first_date, vo2_first = _first(conn, "vo2max_running")
        ftp_date, ftp = _latest(conn, "ftp_watts")

        # Timeline de peso (todos os pontos)
        weight_series = [
            {"date": r["date"], "kg": round(r["weight_g"] / 1000, 1)}
            for r in conn.execute(
                "SELECT date, weight_g FROM biometrics WHERE weight_g IS NOT NULL ORDER BY date"
            )
        ]

    age = _calc_age(prof_dict.get("birth_date") if prof_dict else None)
    weight_kg = (weight_g / 1000) if weight_g else None
    weight_first_kg = (weight_first_g / 1000) if weight_first_g else None
    weight_delta = (
        round(weight_kg - weight_first_kg, 1)
        if weight_kg is not None and weight_first_kg is not None
        else None
    )
    height_m = (height_cm / 100) if height_cm else None
    bmi = round(weight_kg / (height_m * height_m), 1) if weight_kg and height_m else None

    bmi_zone = None
    if bmi:
        if bmi < 18.5:
            bmi_zone = "abaixo"
        elif bmi < 25:
            bmi_zone = "saudavel"
        elif bmi < 30:
            bmi_zone = "sobrepeso"
        else:
            bmi_zone = "obesidade"

    return {
        "available": bool(prof_dict),
        "age": age,
        "gender": prof_dict.get("gender") if prof_dict else None,
        "birth_date": prof_dict.get("birth_date") if prof_dict else None,
        "max_hr_override": prof_dict.get("max_hr_override") if prof_dict else None,
        "weight": {
            "kg": weight_kg,
            "date": weight_date,
            "first_kg": weight_first_kg,
            "first_date": weight_first_date,
            "delta_kg": weight_delta,
            "series": weight_series,
        },
        "height_cm": height_cm,
        "bmi": bmi,
        "bmi_zone": bmi_zone,
        "vo2max": {
            "value": vo2,
            "date": vo2_date,
            "first_value": vo2_first,
            "first_date": vo2_first_date,
            "delta": round(vo2 - vo2_first, 1) if vo2 and vo2_first else None,
        },
        "ftp_watts": ftp,
        "ftp_date": ftp_date,
    }
