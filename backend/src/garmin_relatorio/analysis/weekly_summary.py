"""Resumo semanal de treinos.

Duas implementacoes:
- AI: chama Claude Haiku 4.5 com prompt cacheado, gera texto natural pt-BR
- Template: fallback determinístico sem IA, sempre disponível

A escolha eh feita no endpoint (parametro use_ai). API funciona sem ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

from ..config import config
from . import acwr, garmin_metrics, overtraining, recovery, volume, zones_distribution

log = logging.getLogger(__name__)

# Prompt do sistema. Mantido conciso pra Haiku — o cache_control esta presente
# mas o prefixo so cacheia de fato a partir de ~4096 tokens (silencioso quando
# abaixo). Conforme expandirmos com mais exemplos few-shot, caching ativa sem
# mais mudancas.
SYSTEM_PROMPT = """Voce e um treinador esportivo virtual que escreve resumos semanais \
de treinos pra atletas iniciantes/intermediarios em triathlon. Tom: motivador mas honesto, \
direto, sem firulas. Sempre em portugues brasileiro.

Estrutura do resumo (1-2 paragrafos curtos, max 5 frases no total):
1. Comeca apontando o destaque da semana (volume, consistencia, ou conquista). \
Use numeros concretos (km, treinos, pace).
2. Aponta UM ponto de atenção se houver (ACWR alto, sono ruim, overtraining, \
inconsistência). Se tudo bem, elogia e sugere proxima evolucao.
3. Termina com 1 sugestao acionavel pra proxima semana (ex: \"Adicione 1 treino leve \
de bike\", \"Priorize sono > 7h\", \"Considere 1 dia extra de recuperacao\").

Regras:
- Nao mencione metricas que nao foram fornecidas
- Nao invente dados
- Nao use markdown nem listas — texto corrido
- Evite jargao medico (use \"risco de lesao alto\" em vez de \"ACWR > 1.5\")
- Use \"voce\" (segunda pessoa)
- Ignore semanas sem nenhum treino — apenas mencione descanso brevemente
- Se ACWR estiver \"destreino\" mas a semana ainda esta em andamento, nao alarme
"""


def build_weekly_context(week_offset: int = 0) -> dict[str, Any]:
    """Coleta dados da semana especificada (0 = atual, 1 = anterior, etc)."""
    today = date.today()
    target_monday = today - timedelta(days=today.weekday() + 7 * week_offset)
    target_sunday = target_monday + timedelta(days=6)

    week_volume = volume.latest_week_totals() if week_offset == 0 else None
    if week_offset > 0:
        # Recalcula pegando essa semana especificamente
        all_weeks = volume.weekly_summary(days=7 * (week_offset + 2))
        target_iso = target_monday.isoformat()
        sports: dict[str, dict[str, Any]] = {}
        sessions = duration = distance = 0
        for w in all_weeks:
            if w["week_start"] != target_iso:
                continue
            sports[w["sport"]] = {
                "sessions": w["sessions"],
                "duration_min": w["duration_min"],
                "distance_km": w["distance_km"],
            }
            sessions += w["sessions"]
            duration += w["duration_min"]
            distance += w["distance_km"]
        week_volume = {
            "week_start": target_iso,
            "sessions": sessions,
            "duration_min": round(duration, 1),
            "distance_km": round(distance, 2),
            "by_sport": sports,
        }

    polarization = zones_distribution.polarization_index(days=7 * (week_offset + 1))

    return {
        "week_start": target_monday.isoformat(),
        "week_end": target_sunday.isoformat(),
        "is_current_week": week_offset == 0,
        "volume": week_volume,
        "injury_risk": acwr.current_status(),
        "overtraining": overtraining.overtraining_score(),
        "readiness": recovery.readiness_today(),
        "vo2max_latest": garmin_metrics.latest_vo2max(),
        "garmin_predictions": garmin_metrics.garmin_race_predictions(),
        "polarization": polarization,
    }


def _user_prompt(ctx: dict[str, Any]) -> str:
    """Serializa o contexto pro prompt do user. Filtra ruido."""
    summary: dict[str, Any] = {
        "semana": f"{ctx['week_start']} a {ctx['week_end']}",
        "semana_em_andamento": ctx["is_current_week"],
    }

    vol = ctx["volume"] or {}
    if vol.get("sessions"):
        summary["volume"] = {
            "treinos": vol["sessions"],
            "tempo_total_min": vol["duration_min"],
            "distancia_total_km": vol["distance_km"],
            "por_modalidade": vol.get("by_sport", {}),
        }

    risk = ctx["injury_risk"]
    if risk.get("acwr") is not None:
        summary["risco_lesao"] = {
            "acwr": risk["acwr"],
            "zona": risk["zone"],
        }

    ot = ctx["overtraining"]
    if ot.get("flag") not in (None, "ok"):
        summary["overtraining"] = {
            "score": f"{ot['score']}/{ot['max_score']}",
            "flag": ot["flag"],
            "sinais": [s["msg"] for s in ot.get("signals", [])],
        }

    pol = ctx["polarization"]
    if pol.get("verdict") not in (None, "sem_dados"):
        summary["distribuicao_zonas"] = {
            "z1_z2_pct": pol.get("low_pct"),
            "z3_pct": pol.get("mid_pct"),
            "z4_z5_pct": pol.get("high_pct"),
            "padrao": pol.get("verdict"),
        }

    if ctx["readiness"].get("notes"):
        summary["alertas_recuperacao"] = ctx["readiness"]["notes"]

    vo2 = (ctx["vo2max_latest"].get("by_sport") or {}).get("run")
    if vo2:
        summary["vo2max_corrida"] = vo2["value"]

    pred = ctx["garmin_predictions"].get("predictions") or []
    if pred:
        summary["predicoes_corrida"] = {p["label"]: p["predicted_time_s"] for p in pred[:2]}

    return (
        "Gere o resumo semanal pra esta atleta. Dados:\n\n"
        + json.dumps(summary, ensure_ascii=False, indent=2)
    )


def generate_summary_ai(ctx: dict[str, Any]) -> str:
    """Chama Claude Haiku 4.5 e retorna texto natural pt-BR."""
    if not config.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY nao configurada")

    # Import lazy: nao importa anthropic se a chave nao existir
    from anthropic import Anthropic

    client = Anthropic(api_key=config.anthropic_api_key)

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=600,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": _user_prompt(ctx)}],
    )

    # response.content e lista de blocks; pegamos o text
    for block in response.content:
        if block.type == "text":
            return block.text

    raise RuntimeError("Resposta sem bloco de texto")


def generate_summary_template(ctx: dict[str, Any]) -> str:
    """Fallback sem IA — mais factual, menos natural."""
    parts: list[str] = []
    vol = ctx["volume"] or {}

    if not vol.get("sessions"):
        parts.append(f"Semana {ctx['week_start']} a {ctx['week_end']}: nenhum treino registrado.")
        if ctx["is_current_week"]:
            parts.append("Se foi descanso planejado, ok. Caso contrario, retome com treino leve.")
        return " ".join(parts)

    sessions = vol["sessions"]
    km = vol["distance_km"]
    minutes = vol["duration_min"]
    by_sport = vol.get("by_sport", {})

    sport_summary = ", ".join(
        f"{s['sessions']}× {sport}" for sport, s in by_sport.items() if s["sessions"] > 0
    )
    parts.append(
        f"Voce treinou {sessions} vezes nesta semana ({sport_summary}), "
        f"totalizando {km:.1f}km em {minutes:.0f}min."
    )

    risk = ctx["injury_risk"]
    if risk.get("zone") == "alto":
        parts.append(f"⚠️ Risco de lesao ALTO (ACWR {risk['acwr']}). Reduza volume.")
    elif risk.get("zone") == "moderado":
        parts.append(f"Carga subindo (ACWR {risk['acwr']}). Considere 1 dia extra leve.")
    elif risk.get("zone") == "destreino" and not ctx["is_current_week"]:
        parts.append("Volume baixo essa semana — se nao foi taper planejado, retome gradual.")
    elif risk.get("zone") == "otimo":
        parts.append("Carga em zona otima. Pode manter ou progredir 5-10% na proxima semana.")

    ot = ctx["overtraining"]
    if ot.get("flag") in ("alerta", "vermelho"):
        parts.append(f"Sinais de fadiga: {', '.join(s['msg'] for s in ot['signals'])}.")

    pol = ctx["polarization"]
    if pol.get("verdict") == "limiar":
        parts.append(
            "Muito tempo em Z3 (zona cinza) — considere mais base lenta ou intervalos curtos."
        )

    return " ".join(parts)


def generate_summary(week_offset: int = 0, use_ai: bool = True) -> dict[str, Any]:
    """Endpoint helper: tenta IA, cai no template em qualquer falha."""
    ctx = build_weekly_context(week_offset)

    method = "template"
    text = ""
    error: str | None = None

    if use_ai and config.anthropic_api_key:
        try:
            text = generate_summary_ai(ctx)
            method = "claude-haiku-4-5"
        except Exception as e:
            log.warning("Claude API falhou, usando template: %s", e)
            error = str(e)
            text = generate_summary_template(ctx)
    else:
        text = generate_summary_template(ctx)

    return {
        "week_start": ctx["week_start"],
        "week_end": ctx["week_end"],
        "method": method,
        "text": text,
        "error": error,
        "context_snapshot": ctx,
    }
