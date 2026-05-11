"""Compara predicoes Riegel vs Garmin (FirstBeat)."""
from __future__ import annotations

from . import garmin_metrics, performance


def riegel_vs_garmin() -> dict:
    """Lado a lado pras 4 distancias canonicas."""
    riegel = performance.predict_race("run")
    garmin = garmin_metrics.garmin_race_predictions()

    # Mapa: distance_m -> riegel time
    r_map = {p["distance_m"]: p for p in riegel["predictions"]}
    g_map = {p["distance_m"]: p for p in garmin["predictions"]}

    distances = [(5000, "5K"), (10000, "10K"), (21097, "21K"), (42195, "Maratona")]

    rows = []
    for dist, label in distances:
        r = r_map.get(dist)
        g = g_map.get(dist)
        if not r and not g:
            continue
        diff_s = (r["predicted_time_s"] - g["predicted_time_s"]) if (r and g) else None
        rows.append({
            "label": label,
            "distance_m": dist,
            "riegel_s": r["predicted_time_s"] if r else None,
            "riegel_pace": r["predicted_pace_s_km"] if r else None,
            "riegel_confidence": r.get("confidence") if r else None,
            "garmin_s": g["predicted_time_s"] if g else None,
            "garmin_pace": g["predicted_pace_s_km"] if g else None,
            "diff_s": diff_s,
        })

    return {
        "riegel_reference": riegel.get("reference"),
        "garmin_date": garmin.get("date"),
        "rows": rows,
    }
