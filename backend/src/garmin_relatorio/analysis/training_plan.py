"""Plano semanal sugerido.

Combina ACWR atual, overtraining score, fase de prova mais proxima e volume da
ultima semana para sugerir treinos da proxima semana. Heuristica simples, sem ML.

Logica:
- ACWR > 1.5 ou overtraining "vermelho/alerta" -> reduz carga (target 70-85%)
- ACWR < 0.8 -> retomada gradual (target 110-120% se overtraining ok)
- Sweet spot (0.8-1.3) e overtraining ok -> progride 5-10% (target 105-110%)
- Fase TAPER -> impoe -30 a -40% independente do ACWR
- Fase BUILD -> aumenta % intensidade (Z4)
- Fase PEAK -> mantem volume, foco em treino especifico
- Fase RACE WEEK -> descanso ativo
- Fase BASE / manutencao -> volume aerobico, 80/20 polarizado

A duracao total sugerida vem do volume da semana passada por modalidade
multiplicado pelo target_load_pct.

Sessoes-chave sao recomendadas explicitamente: longao (sempre), tempo (build+),
intervalo (build/peak).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from . import acwr, overtraining, races, volume, zones_distribution


REST_DAYS_BY_FLAG = {"ok": 1, "atencao": 2, "alerta": 3, "vermelho": 4}

DAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
SPORT_ICON = {"run": "🏃", "bike": "🚴", "swim": "🏊", "rest": "😴"}


def weekly_plan() -> dict[str, Any]:
    today = date.today()
    next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)

    last_week = _last_week_by_sport()
    risk = acwr.current_status()
    overt = overtraining.overtraining_score()
    upcoming_race = _next_race()
    phase = upcoming_race["phase"] if upcoming_race else "manutencao"

    target_pct, target_reason = _target_load_pct(risk, overt, phase)
    intensity = _intensity_mix(phase, overt["flag"])
    rest_days = REST_DAYS_BY_FLAG.get(overt["flag"], 1)
    if phase == "taper":
        rest_days = max(rest_days, 2)
    if phase == "race_week":
        rest_days = max(rest_days, 3)

    sessions_by_sport = _sessions_by_sport(last_week, target_pct, phase)
    key_sessions = _key_sessions(phase, overt["flag"], sessions_by_sport)
    warnings = _warnings(risk, overt, phase)
    pol = zones_distribution.polarization_index(28)
    schedule = _build_schedule(
        sessions_by_sport,
        key_sessions,
        rest_days,
        phase,
        overt["flag"],
        upcoming_race,
        next_monday,
    )

    return {
        "week_start": next_monday.isoformat(),
        "phase": phase,
        "phase_reason": (
            f"{upcoming_race['name']} em {upcoming_race['days_to']}d"
            if upcoming_race
            else "Sem prova proxima — manutencao"
        ),
        "target_load_pct": target_pct,
        "target_reason": target_reason,
        "sessions_by_sport": sessions_by_sport,
        "intensity_mix": intensity,
        "key_sessions": key_sessions,
        "rest_days": rest_days,
        "warnings": warnings,
        "polarization_now": pol.get("verdict"),
        "last_week_load": _last_week_total(last_week),
        "schedule": schedule,
    }


def _last_week_by_sport() -> dict[str, dict[str, float]]:
    """Volume da ultima semana fechada (segunda passada -> domingo passado)."""
    weekly = volume.weekly_summary(days=21)
    if not weekly:
        return {}
    today = date.today()
    this_week_start = (today - timedelta(days=today.weekday())).isoformat()
    last_week_start = (
        today - timedelta(days=today.weekday() + 7)
    ).isoformat()

    out: dict[str, dict[str, float]] = {}
    for row in weekly:
        if row["week_start"] == last_week_start:
            out[row["sport"]] = {
                "sessions": row["sessions"],
                "duration_min": row["duration_min"],
                "distance_km": row["distance_km"],
            }
    if not out:
        # fallback: usa semana corrente projetada se nao houver semana fechada
        for row in weekly:
            if row["week_start"] == this_week_start:
                out[row["sport"]] = {
                    "sessions": row["sessions"],
                    "duration_min": row["duration_min"],
                    "distance_km": row["distance_km"],
                }
    return out


def _last_week_total(last_week: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        "sessions": int(sum(s["sessions"] for s in last_week.values())),
        "duration_min": round(sum(s["duration_min"] for s in last_week.values()), 1),
        "distance_km": round(sum(s["distance_km"] for s in last_week.values()), 2),
    }


def _next_race() -> dict | None:
    upcoming = races.list_races(include_past=False)
    return upcoming[0] if upcoming else None


def _target_load_pct(risk: dict, overt: dict, phase: str) -> tuple[int, str]:
    flag = overt.get("flag", "ok")
    zone = risk.get("zone", "indefinido")

    if phase == "race_week":
        return 50, "Semana da prova — descanso ativo."
    if phase == "taper":
        return 65, "Taper: -35% mantendo intensidade pra chegar afiada."
    if flag == "vermelho":
        return 60, "Overtraining vermelho — corte forte de carga."
    if flag == "alerta":
        return 75, "Multiplos sinais de fadiga — reduz 25%."
    if zone == "alto":
        return 80, "ACWR alto (>1.5): reduz 20% pra sair da faixa de risco."
    if zone == "moderado":
        return 95, "ACWR moderado: mantem proximo ao atual, sem progredir."
    if zone == "destreino":
        if flag == "ok":
            return 115, "ACWR baixo + recuperada: retomada gradual (+15%)."
        return 100, "ACWR baixo mas algum sinal de fadiga — mantem."
    if zone == "otimo" and flag in {"ok", "atencao"}:
        if phase == "peak":
            return 105, "Peak: pequena progressao (+5%), foco em especificidade."
        if phase == "build":
            return 110, "Build + ACWR otimo: progride 10%."
        return 107, "Sweet spot: progride 5-10%."
    return 100, "Mantem carga atual."


def _intensity_mix(phase: str, flag: str) -> dict[str, int]:
    """% sugerido em zonas baixas (Z1-Z2), media (Z3) e alta (Z4-Z5).

    Soma sempre 100.
    """
    if flag in {"alerta", "vermelho"} or phase == "race_week":
        return {"low": 90, "mid": 10, "high": 0}
    if phase == "taper":
        return {"low": 75, "mid": 10, "high": 15}
    if phase == "peak":
        return {"low": 70, "mid": 15, "high": 15}
    if phase == "build":
        return {"low": 75, "mid": 15, "high": 10}
    # base / manutencao -> polarizado 80/20
    return {"low": 80, "mid": 10, "high": 10}


def _sessions_by_sport(
    last_week: dict[str, dict[str, float]],
    target_pct: int,
    phase: str,
) -> list[dict]:
    factor = target_pct / 100.0
    if not last_week:
        # cold-start: triathlete baseline 3/2/2 escalado pelo target
        baseline = [
            ("run", 3, 150.0, 25.0),
            ("bike", 2, 150.0, 50.0),
            ("swim", 2, 90.0, 4.0),
        ]
        return [
            {
                "sport": sp,
                "sessions": max(1, round(sess * factor)),
                "duration_min": round(dur * factor, 1),
                "distance_km": round(dist * factor, 2),
            }
            for sp, sess, dur, dist in baseline
        ]

    out = []
    for sport in ("run", "bike", "swim"):
        prev = last_week.get(sport)
        if not prev:
            continue
        sessions = max(1, round(prev["sessions"] * factor))
        if phase == "race_week" and sport == "run":
            sessions = min(sessions, 2)
        out.append({
            "sport": sport,
            "sessions": int(sessions),
            "duration_min": round(prev["duration_min"] * factor, 1),
            "distance_km": round(prev["distance_km"] * factor, 2),
        })
    return out


def _key_sessions(phase: str, flag: str, sessions_by_sport: list[dict]) -> list[dict]:
    run = next((s for s in sessions_by_sport if s["sport"] == "run"), None)
    sessions: list[dict] = []

    if flag in {"alerta", "vermelho"} or phase == "race_week":
        sessions.append({
            "kind": "long_easy",
            "label": "Longão tranquilo Z1-Z2",
            "target": "60-75 min, FC < 75% max — recuperacao ativa",
        })
        return sessions

    if run:
        if phase == "taper":
            sessions.append({
                "kind": "race_pace_short",
                "label": "Bloco curto em pace de prova",
                "target": "10-15 min no ritmo objetivo, sem fadigar",
            })
        elif phase == "peak":
            sessions.append({
                "kind": "race_simulation",
                "label": "Simulacao de prova",
                "target": "Bloco no pace alvo (60-70% da distancia da prova)",
            })
        elif phase == "build":
            sessions.append({
                "kind": "tempo",
                "label": "Tempo run (Z3)",
                "target": "20-30 min continuo no limiar",
            })
            sessions.append({
                "kind": "intervals",
                "label": "Intervalos curtos (Z4)",
                "target": "6-8 × 400m com 90s rec",
            })
        else:  # base/manutencao
            sessions.append({
                "kind": "long_aerobic",
                "label": "Longão aerobico Z1-Z2",
                "target": "60-90 min em FC baixa, construir base",
            })
            sessions.append({
                "kind": "strides",
                "label": "Strides ao fim do facil",
                "target": "6 × 20s strong, recuperacao total",
            })
    return sessions


def _empty_day(idx: int) -> dict:
    return {
        "day_idx": idx,
        "day_label": DAY_LABELS[idx],
        "sport": None,
        "kind": None,
        "label": None,
        "duration_min": 0,
        "distance_km": None,
        "zone": None,
        "target": None,
        "icon": None,
    }


def _set_day(day: dict, **kwargs: Any) -> None:
    day.update(kwargs)
    if kwargs.get("sport"):
        day["icon"] = SPORT_ICON.get(kwargs["sport"])
    elif kwargs.get("kind") == "rest":
        day["icon"] = SPORT_ICON["rest"]


def _race_day_idx(next_monday: date, race: dict | None) -> int | None:
    if not race:
        return None
    race_date = date.fromisoformat(race["race_date"])
    delta = (race_date - next_monday).days
    if 0 <= delta <= 6:
        return delta
    return None


def _race_week_schedule(
    sessions_by_sport: list[dict],
    next_monday: date,
    race: dict,
) -> list[dict]:
    """Template race-week padrao (prova num dia 0..6 da semana).

    D-0   prova
    D-1   descanso passivo
    D-2   shake-out 20min Z2 + 4 strides
    D-3   pre-shake 30min Z2 (corrida facil)
    D-4   descanso
    D-5   nado tecnico recuperativo
    D-6   pre-semana ~45min Z2
    """
    race_idx = _race_day_idx(next_monday, race)
    schedule = [_empty_day(i) for i in range(7)]
    if race_idx is None:
        return schedule

    race_name = race.get("name", "Prova")
    race_dist_km = (race.get("distance_m") or 0) / 1000 or None
    _set_day(
        schedule[race_idx],
        sport=race.get("sport") or "run",
        kind="race",
        label=race_name,
        duration_min=0,
        distance_km=race_dist_km,
        zone="Race",
        target=f"Prova: {race_name}",
    )

    plan = [
        (-1, "rest", None, "Descanso passivo", 0, None, "Hidratação, comida conhecida, sono cedo"),
        (-2, "shake_out", "run", "Shake-out", 20, 3.0, "20 min Z2 + 4×20s strides — sentir as pernas"),
        (-3, "easy", "run", "Easy curto", 30, 4.5, "30 min Z2 leve — sem fadigar"),
        (-4, "rest", None, "Descanso", 0, None, "Descanso ou caminhada leve"),
        (-5, "tech", "swim", "Nado técnico", 30, 1.2, "30 min Z1-Z2, drills suaves"),
        (-6, "easy", "run", "Pré-semana", 45, 6.5, "45 min Z2 confortável"),
    ]
    for offset, kind, sport, label, dur, dist, target in plan:
        idx = race_idx + offset
        if idx < 0 or idx > 6:
            continue
        if schedule[idx]["kind"]:  # nao sobrepor
            continue
        zone = "Z2" if kind in ("easy", "shake_out", "tech") else None
        _set_day(
            schedule[idx],
            sport=sport,
            kind=kind,
            label=label,
            duration_min=dur,
            distance_km=dist,
            zone=zone,
            target=target,
        )

    # qualquer dia ainda vazio = descanso
    for d in schedule:
        if not d["kind"]:
            _set_day(d, kind="rest", label="Descanso", target="Recuperação")
    return schedule


def _build_schedule(
    sessions_by_sport: list[dict],
    key_sessions: list[dict],
    rest_days: int,
    phase: str,
    flag: str,
    race: dict | None,
    next_monday: date,
) -> list[dict]:
    """Distribui as sessoes propostas em 7 dias (Seg=0 .. Dom=6).

    Regras:
    - Hard nunca em dias consecutivos
    - Longao em Sab (corrida); long bike em Dom
    - Rest preferindo Seg, depois Sex
    - Race week tem template proprio (_race_week_schedule)
    """
    if phase == "race_week" and race:
        race_idx = _race_day_idx(next_monday, race)
        if race_idx is not None:
            return _race_week_schedule(sessions_by_sport, next_monday, race)

    schedule = [_empty_day(i) for i in range(7)]
    budget = {s["sport"]: s["sessions"] for s in sessions_by_sport}
    total_dur = {s["sport"]: s["duration_min"] for s in sessions_by_sport}
    total_dist = {s["sport"]: s["distance_km"] for s in sessions_by_sport}
    used_dur = {"run": 0.0, "bike": 0.0, "swim": 0.0}
    used_dist = {"run": 0.0, "bike": 0.0, "swim": 0.0}

    has_tempo = any(k["kind"] == "tempo" for k in key_sessions)
    has_intervals = any(k["kind"] == "intervals" for k in key_sessions)
    has_strides = any(k["kind"] == "strides" for k in key_sessions)
    has_race_sim = any(k["kind"] in ("race_simulation", "race_pace_short") for k in key_sessions)
    long_kind = next(
        (k["kind"] for k in key_sessions if k["kind"] in ("long_aerobic", "long_easy", "race_simulation")),
        "long_aerobic" if budget.get("run", 0) >= 2 else None,
    )

    # Duração teto fixa para sessões "hard curtas" — independe do volume total
    FIXED_CAP = {"tempo": 35, "intervals": 40, "race_pace": 25, "shake_out": 20}

    def _alloc(sport: str, day: int, kind: str, label: str, frac: float, zone: str, target: str) -> None:
        if budget.get(sport, 0) <= 0:
            return
        total_d = total_dur.get(sport) or 0
        total_k = total_dist.get(sport) or 0
        is_last = budget[sport] == 1
        cap = FIXED_CAP.get(kind)
        if cap is not None:
            dur = min(cap, total_d * frac) if not is_last else min(cap, max(0, total_d - used_dur[sport]))
            dist = (dur / total_d) * total_k if total_d > 0 and total_k else None
        elif is_last:
            dur = max(0, total_d - used_dur[sport])
            dist = max(0, total_k - used_dist[sport]) if total_k else None
        else:
            dur = total_d * frac
            dist = total_k * frac if total_k else None
        dur_rounded = round(dur, 0) or (30 if sport != "bike" else 45)
        dist_rounded = round(dist, 1) if dist else None
        _set_day(
            schedule[day], sport=sport, kind=kind, label=label,
            duration_min=dur_rounded, distance_km=dist_rounded, zone=zone, target=target,
        )
        budget[sport] -= 1
        used_dur[sport] += dur_rounded
        if dist_rounded:
            used_dist[sport] += dist_rounded

    def _alloc_run(day, kind, label, frac, zone, target):
        _alloc("run", day, kind, label, frac, zone, target)

    def _alloc_bike(day, kind, label, frac, zone, target):
        _alloc("bike", day, kind, label, frac, zone, target)

    def _alloc_swim(day: int, kind: str = "tech", label: str = "Nado técnico") -> None:
        if budget.get("swim", 0) <= 0:
            return
        remaining = budget["swim"]
        # divide volume restante igualmente entre as sessoes que faltam
        remaining_dur = max(0, (total_dur.get("swim") or 0) - used_dur["swim"])
        remaining_dist = max(0, (total_dist.get("swim") or 0) - used_dist["swim"])
        dur = round(remaining_dur / remaining, 0) if remaining else 45
        dist = round(remaining_dist / remaining, 2) if remaining and remaining_dist else None
        _set_day(
            schedule[day], sport="swim", kind=kind, label=label,
            duration_min=dur, distance_km=dist, zone="Z2",
            target=f"{dur:.0f} min — drills + main set",
        )
        budget["swim"] -= 1
        used_dur["swim"] += dur
        if dist:
            used_dist["swim"] += dist

    # 1. Longão (preferindo Sáb=5 pra run; Dom=6 pra bike se houver 2+ bikes)
    if long_kind and budget.get("run", 0) > 0:
        long_label = {
            "long_aerobic": "Longão Z1-Z2",
            "long_easy": "Longão tranquilo",
            "race_simulation": "Simulação de prova",
        }.get(long_kind, "Longão Z1-Z2")
        long_zone = "Z1-Z2" if long_kind != "race_simulation" else "Race pace"
        _alloc_run(
            5, "long", long_label, 0.45, long_zone,
            f"~{round(total_dur.get('run', 0) * 0.45)}min — base aeróbica" if long_kind != "race_simulation"
            else "Bloco no pace alvo",
        )

    # 2. Tempo run (Ter=1)
    if has_tempo and budget.get("run", 0) > 0:
        _alloc_run(1, "tempo", "Tempo run", 0.22, "Z3", "20-30 min contínuo no limiar")

    # 3. Race-pace bloco (Ter=1 se ainda vazio) — para peak/taper
    if has_race_sim and not schedule[1]["kind"] and budget.get("run", 0) > 0:
        _alloc_run(1, "race_pace", "Pace de prova", 0.18, "Z3-Z4", "10-15 min no ritmo objetivo")

    # 4. Intervalos (Qui=3)
    if has_intervals and budget.get("run", 0) > 0:
        _alloc_run(3, "intervals", "Intervalos", 0.18, "Z4", "6-8×400m com 90s rec")

    # 5. Long bike em Dom=6 se 2+ bikes; senão easy bike
    if budget.get("bike", 0) >= 2:
        _alloc_bike(6, "long", "Bike longa", 0.55, "Z2", "Volume aeróbico — endurance da bike")
    elif budget.get("bike", 0) >= 1 and not schedule[6]["kind"]:
        _alloc_bike(6, "easy", "Bike Z2", 1.0, "Z2", "Recuperativo")

    # 6. Easy bike em Qua=2
    if budget.get("bike", 0) > 0 and not schedule[2]["kind"]:
        frac = 1.0 if budget["bike"] == 1 else 0.45
        _alloc_bike(2, "easy", "Bike Z2", frac, "Z2", "Aeróbico moderado")

    # 7. Swims em Ter/Qui/Sex preferindo dias com baixa carga
    swim_slot_order = [1, 3, 4, 2]  # Ter, Qui, Sex, Qua
    for d in swim_slot_order:
        if budget.get("swim", 0) <= 0:
            break
        # nao colocar swim no mesmo dia de hard run a menos que precise
        if schedule[d]["kind"] in ("tempo", "intervals", "race_pace") and budget["swim"] > (7 - d - rest_days):
            continue
        if schedule[d]["kind"]:
            continue
        _alloc_swim(d)

    # 8. Easy runs preenchendo budget restante (Qua=2, Sex=4)
    easy_run_slots = [2, 4, 6]
    if has_strides:
        strides_alloc = False
        for d in easy_run_slots:
            if budget.get("run", 0) <= 0:
                break
            if schedule[d]["kind"]:
                continue
            label = "Easy + strides" if not strides_alloc else "Easy run"
            target = "Z2 + 6×20s strides ao final" if not strides_alloc else "Z2 confortável"
            _alloc_run(d, "easy", label, 0.18, "Z2", target)
            strides_alloc = strides_alloc or label == "Easy + strides"
    else:
        for d in easy_run_slots:
            if budget.get("run", 0) <= 0:
                break
            if schedule[d]["kind"]:
                continue
            _alloc_run(d, "easy", "Easy run", 0.18, "Z2", "Z2 confortável")

    # 9. Swims remanescentes em qualquer lugar livre
    for d in range(7):
        if budget.get("swim", 0) <= 0:
            break
        if not schedule[d]["kind"]:
            _alloc_swim(d)

    # 10. Bikes remanescentes
    for d in [4, 2, 0]:
        if budget.get("bike", 0) <= 0:
            break
        if not schedule[d]["kind"]:
            _alloc_bike(d, "easy", "Bike Z2", 1.0, "Z2", "Aeróbico leve")

    # 11. Runs remanescentes
    for d in [6, 4, 2, 0]:
        if budget.get("run", 0) <= 0:
            break
        if not schedule[d]["kind"]:
            _alloc_run(d, "easy", "Easy run", 0.15, "Z2", "Z2 confortável")

    # 12. Marcar rest_days nos vazios — preferir Seg, depois Sex, depois Dom
    rest_priority = [0, 4, 6, 2, 3, 1, 5]
    rest_placed = 0
    for d in rest_priority:
        if rest_placed >= rest_days:
            break
        if not schedule[d]["kind"]:
            _set_day(
                schedule[d], kind="rest", label="Descanso",
                target="Descanso passivo ou caminhada leve",
            )
            rest_placed += 1

    # 13. Qualquer dia ainda vazio: descanso flex
    for d in schedule:
        if not d["kind"]:
            _set_day(d, kind="rest", label="Flex", target="Reservado — opção de cross-training ou off")

    return schedule


def _warnings(risk: dict, overt: dict, phase: str) -> list[str]:
    out: list[str] = []
    if risk.get("zone") == "alto":
        out.append("ACWR acima de 1.5: alto risco de lesao se mantiver carga.")
    if overt.get("flag") == "vermelho":
        out.append("Overtraining vermelho — considere descanso passivo 1-2 dias.")
    elif overt.get("flag") == "alerta":
        out.append("Multiplos sinais de fadiga — priorize sono e sessoes Z1-Z2.")
    if phase in {"peak", "taper", "race_week"}:
        out.append(f"Fase {phase} — evitar sessoes novas/desconhecidas.")
    return out
