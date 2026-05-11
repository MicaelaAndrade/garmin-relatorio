"""Wrapper de ingest diario para uso via cron / systemd timer.

Executa em sequencia (best-effort) e nunca aborta a sequencia inteira por uma
fonte falhar. Loga cada etapa em backend/data/cron.log + stdout.

Decisao por fonte:
- Garmin: roda se GARMIN_EMAIL e GARMIN_PASSWORD configurados
- Strava: roda se backend/data/strava_token.json existir
- .fit: roda se houver arquivos em backend/data/exports/
- export GDPR: NUNCA roda automatico (e' carga manual e pesada)

Saida: codigo 0 mesmo com falhas individuais (logadas). So retorna != 0 se
nenhum ingest pode rodar (todas fontes desabilitadas).
"""
from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

from ..config import ROOT, config

LOG_FILE = ROOT / "backend" / "data" / "cron.log"


def _setup_log() -> logging.Logger:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("garmin_relatorio.cron")
    log.setLevel(logging.INFO)
    # Reset handlers caso o setLogger global ja tenha configurado
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(fmt)
    log.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(sh)
    log.propagate = False
    return log


def _safe(log: logging.Logger, label: str, fn) -> bool:
    log.info("→ %s", label)
    try:
        result = fn()
        log.info("  ok: %s", result)
        return True
    except Exception as exc:
        log.error("  falhou: %s", exc)
        log.debug("%s", traceback.format_exc())
        return False


def run(days: int = 7) -> int:
    log = _setup_log()
    log.info("=== cron-ingest iniciado em %s (janela %dd) ===", datetime.now().isoformat(timespec="seconds"), days)

    any_attempted = False
    failures = 0

    # Garmin live
    if config.garmin_email and config.garmin_password:
        from . import garmin

        any_attempted = True
        if not _safe(log, "Garmin: atividades", lambda: garmin.ingest_activities(days=days)):
            failures += 1
        if not _safe(log, "Garmin: sono", lambda: garmin.ingest_sleep(days=min(days, 30))):
            failures += 1
        if not _safe(log, "Garmin: metricas diarias", lambda: garmin.ingest_daily(days=min(days, 30))):
            failures += 1
        if not _safe(log, "Garmin: workouts agendados", lambda: garmin.ingest_scheduled_workouts(months_ahead=2)):
            failures += 1
        if not _safe(log, "Garmin: detalhes dos workouts", lambda: garmin.ingest_workout_details()):
            failures += 1
    else:
        log.info("Garmin: GARMIN_EMAIL/PASSWORD nao configurados, pulando.")

    # Strava
    strava_token = ROOT / "backend" / "data" / "strava_token.json"
    if strava_token.exists() and config.strava_client_id and config.strava_client_secret:
        from . import strava

        any_attempted = True
        if not _safe(log, "Strava: atividades", lambda: strava.ingest_activities(days=days)):
            failures += 1
    else:
        log.info("Strava: token ou credenciais ausentes, pulando.")

    # .fit manuais
    fit_dir = ROOT / "backend" / "data" / "exports"
    fit_files_count = sum(1 for _ in fit_dir.glob("*.fit")) if fit_dir.exists() else 0
    if fit_files_count > 0:
        from . import fit_files

        any_attempted = True
        if not _safe(log, f"FIT: {fit_files_count} arquivo(s)", lambda: fit_files.ingest_directory()):
            failures += 1
    else:
        log.info("FIT: nenhum arquivo em backend/data/exports/, pulando.")

    if not any_attempted:
        log.warning("Nenhuma fonte configurada — nada a fazer.")
        return 2

    log.info("=== cron-ingest finalizado — %d falha(s) ===", failures)
    return 0
