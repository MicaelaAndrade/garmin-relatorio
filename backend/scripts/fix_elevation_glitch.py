"""Migracao one-time: nulifica elevation_gain corrompido pelo altimetro barometrico.

Contexto: o altimetro barometrico do relogio comecou a falhar em 25/out/2025,
gravando elevation_gain internamente inconsistente (grade impossivel, barometro
flat-lined max==min, ou sentinela -500). Esses valores NAO sao recuperaveis por
conversao de unidade — sao lixo de sensor. A correcao honesta e' nulifica-los.

Criterio: grade implicito = elevation_gain / distancia_km. Atividades pre-glitch
nunca passaram de ~40 m/km, entao o corte em 60 m/km separa limpo de lixo sem
falso positivo. Idempotente: linhas ja nulas ou plausiveis nao mudam.

Uso: uv run python scripts/fix_elevation_glitch.py [--apply]
Sem --apply, roda em dry-run (so mostra o que faria).
"""
from __future__ import annotations

import sys

from garmin_relatorio.db import connect

GRADE_LIMIT_M_PER_KM = 60.0


def main(apply: bool) -> None:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, sport, started_at, distance_m, elevation_gain
            FROM activities
            WHERE elevation_gain IS NOT NULL AND distance_m > 500
            """
        ).fetchall()

        to_null: list[int] = []
        for r in rows:
            grade = r["elevation_gain"] / (r["distance_m"] / 1000)
            if grade > GRADE_LIMIT_M_PER_KM:
                to_null.append(r["id"])

        print(f"Atividades com elevação: {len(rows)}")
        print(f"Marcadas como lixo de sensor (grade > {GRADE_LIMIT_M_PER_KM:.0f} m/km): {len(to_null)}")

        if not apply:
            print("\n[DRY-RUN] Nada gravado. Rode com --apply pra nulificar.")
            return

        conn.executemany(
            "UPDATE activities SET elevation_gain = NULL WHERE id = ?",
            [(i,) for i in to_null],
        )
        conn.commit()
        print(f"\n✓ {len(to_null)} linhas com elevation_gain nulificadas.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
