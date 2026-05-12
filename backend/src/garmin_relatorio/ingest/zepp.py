"""Ingest do export do Zepp Life (Mi Body Composition Scale 2 e similares).

O Zepp Life permite exportar todos os dados em CSV via Perfil > Configuracoes >
Conta Mi Fitness > Sobre > Exportar dados. Gera um diretorio com varias subpastas
(BODY, SLEEP, HEARTRATE, etc). Por enquanto so' suportamos BODY (balanca de
bioimpedancia).

Uso:
    uv run garmin-relatorio ingest-zepp /path/to/3312646638_xxxxx
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..db import connect

log = logging.getLogger(__name__)


def _parse_float(v: str) -> float | None:
    if not v or v.lower() in ("null", "none", ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_iso_utc(ts: str) -> str | None:
    """Zepp grava timezone '+0000' (sem :). Normaliza para ISO 8601."""
    if not ts:
        return None
    ts = ts.strip()
    # '2026-03-17 14:47:42+0000' -> '2026-03-17T14:47:42+00:00'
    if " " in ts:
        ts = ts.replace(" ", "T", 1)
    if len(ts) >= 5 and ts[-5] in ("+", "-") and ts[-3] != ":":
        ts = ts[:-2] + ":" + ts[-2:]
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def ingest_body(zepp_root: Path) -> dict[str, int]:
    """Le BODY/BODY_*.csv e popula body_composition."""
    body_dir = zepp_root / "BODY"
    if not body_dir.exists():
        log.warning("Zepp: BODY dir nao encontrado em %s", body_dir)
        return {"inserted": 0, "skipped": 0, "errors": 0}

    csv_files = sorted(body_dir.glob("BODY_*.csv"))
    if not csv_files:
        log.warning("Zepp: nenhum BODY_*.csv em %s", body_dir)
        return {"inserted": 0, "skipped": 0, "errors": 0}

    inserted = skipped = errors = 0
    with connect() as conn:
        for csv_path in csv_files:
            with csv_path.open(encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    measured_at = _parse_iso_utc(row.get("time", ""))
                    weight = _parse_float(row.get("weight", ""))
                    if not measured_at or not weight:
                        errors += 1
                        continue
                    payload = {
                        "source": "zepp",
                        "measured_at": measured_at,
                        "weight_kg": weight,
                        "height_cm": _parse_float(row.get("height", "")),
                        "bmi": _parse_float(row.get("bmi", "")),
                        "fat_pct": _parse_float(row.get("fatRate", "")),
                        "water_pct": _parse_float(row.get("bodyWaterRate", "")),
                        "muscle_pct": _parse_float(row.get("muscleRate", "")),
                        "bone_mass_kg": _parse_float(row.get("boneMass", "")),
                        "bmr_kcal": (
                            int(_parse_float(row.get("metabolism", "")) or 0) or None
                        ),
                        "visceral_fat": _parse_float(row.get("visceralFat", "")),
                        "raw": json.dumps(row, ensure_ascii=False),
                    }
                    cur = conn.execute(
                        """
                        INSERT INTO body_composition (
                            source, measured_at, weight_kg, height_cm, bmi,
                            fat_pct, water_pct, muscle_pct, bone_mass_kg,
                            bmr_kcal, visceral_fat, raw
                        ) VALUES (
                            :source, :measured_at, :weight_kg, :height_cm, :bmi,
                            :fat_pct, :water_pct, :muscle_pct, :bone_mass_kg,
                            :bmr_kcal, :visceral_fat, :raw
                        )
                        ON CONFLICT(source, measured_at) DO UPDATE SET
                            weight_kg=excluded.weight_kg,
                            bmi=excluded.bmi,
                            fat_pct=COALESCE(excluded.fat_pct, body_composition.fat_pct),
                            water_pct=COALESCE(excluded.water_pct, body_composition.water_pct),
                            muscle_pct=COALESCE(excluded.muscle_pct, body_composition.muscle_pct),
                            bone_mass_kg=COALESCE(excluded.bone_mass_kg, body_composition.bone_mass_kg),
                            bmr_kcal=COALESCE(excluded.bmr_kcal, body_composition.bmr_kcal),
                            visceral_fat=COALESCE(excluded.visceral_fat, body_composition.visceral_fat),
                            raw=excluded.raw
                        """,
                        payload,
                    )
                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        skipped += 1

    log.info(
        "Zepp BODY: %d inseridas, %d atualizadas/duplicadas, %d com erro",
        inserted, skipped, errors,
    )
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


def ingest_all(zepp_root: Path) -> dict[str, dict]:
    """Roda todos os ingests Zepp suportados. Hoje so' BODY."""
    if not zepp_root.exists():
        raise FileNotFoundError(f"Zepp export dir nao encontrado: {zepp_root}")
    return {"body": ingest_body(zepp_root)}
