"""Seed das provas alvo. Idempotente — pode rodar varias vezes.

Edite SEED_RACES com as provas em que voce pretende competir. As datas/locais
abaixo sao exemplos baseados no setup inicial; personalize livremente.
"""
from __future__ import annotations

import logging

from ..db import connect

log = logging.getLogger(__name__)

# (name, date, sport, distance_m, swim_m, bike_m, run_m, location, is_confirmed)
SEED_RACES: list[tuple] = [
    ("Sao Joaquim Run Franca", "2026-05-24", "run", 5000, None, None, None, "Franca", 1),
    ("SESC Franca", "2026-05-31", "run", 6000, None, None, None, "Franca", 1),
    ("Meia Maratona SP City", "2026-07-26", "run", 21097, None, None, None, "Sao Paulo", 1),
    ("Corrida Netshoes", "2026-08-23", "run", 10000, None, None, None, "TBD", 1),
    ("Corrida Live", "2026-08-30", "run", 6000, None, None, None, "Ribeirao Preto", 1),
    ("Triathlon Sprint", "2026-09-30", "triathlon", 5000, 750, 20000, 5000, "TBD", 0),
]


def seed_races() -> dict[str, int]:
    inserted = updated = 0
    with connect() as conn:
        for r in SEED_RACES:
            existing = conn.execute(
                "SELECT id FROM races WHERE name = ? AND race_date = ?",
                (r[0], r[1]),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE races SET sport=?, distance_m=?, triathlon_swim_m=?,
                        triathlon_bike_m=?, triathlon_run_m=?, location=?, is_confirmed=?
                    WHERE id=?
                    """,
                    (r[2], r[3], r[4], r[5], r[6], r[7], r[8], existing["id"]),
                )
                updated += 1
            else:
                conn.execute(
                    """
                    INSERT INTO races
                    (name, race_date, sport, distance_m, triathlon_swim_m,
                     triathlon_bike_m, triathlon_run_m, location, is_confirmed)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    r,
                )
                inserted += 1
    log.info("Races seed: %d inseridas, %d atualizadas", inserted, updated)
    return {"inserted": inserted, "updated": updated}
