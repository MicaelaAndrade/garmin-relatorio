"""CLI principal: ingesta dados e roda servidor."""
from __future__ import annotations

import argparse
import logging
import sys

from .config import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="garmin-relatorio")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_garmin = sub.add_parser("ingest-garmin", help="Puxa dados do Garmin Connect")
    p_garmin.add_argument("--days", type=int, default=90)
    p_garmin.add_argument(
        "--what",
        choices=["all", "activities", "sleep", "daily", "scheduled", "workouts"],
        default="all",
    )

    sub.add_parser("strava-auth", help="Roda fluxo OAuth do Strava (1x)")
    p_strava = sub.add_parser("ingest-strava", help="Puxa atividades do Strava")
    p_strava.add_argument("--days", type=int, default=90)

    sub.add_parser("ingest-fit", help="Importa arquivos .fit de backend/data/exports/")

    p_export = sub.add_parser(
        "ingest-export",
        help="Le export GDPR do Garmin (configurar GARMIN_EXPORT_DIR no .env)",
    )
    p_export.add_argument(
        "--what",
        choices=["all", "activities", "sleep", "daily", "vo2max", "predictions", "menstrual", "profile", "biometrics"],
        default="all",
    )

    sub.add_parser(
        "seed-races",
        help="Popula tabela races com as provas alvo (idempotente)",
    )

    p_cron = sub.add_parser(
        "cron-ingest",
        help="Ingest diario best-effort (Garmin + Strava + .fit). Loga em backend/data/cron.log",
    )
    p_cron.add_argument("--days", type=int, default=7)

    p_zepp = sub.add_parser(
        "ingest-zepp",
        help="Importa export do Zepp Life (Mi Body Composition Scale 2 etc)",
    )
    p_zepp.add_argument("path", help="Path do diretório do export (ex: ~/Downloads/3312646638_xxxx)")

    p_mfit = sub.add_parser(
        "import-mfit",
        help="Importa PDF do MFit Personal (fortalecimento)",
    )
    p_mfit.add_argument("source", help="Path local OU URL do PDF (secureupload.mfitpersonal.com.br)")
    p_mfit.add_argument(
        "--weekdays",
        help="Mapeamento ordem->weekday, ex: '1:0,2:4' (rotina 1 Seg, rotina 2 Sex). Default Seg/Sex.",
    )

    p_serve = sub.add_parser("serve", help="Sobe API FastAPI")
    p_serve.add_argument("--reload", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "ingest-garmin":
        from .ingest import garmin

        if args.what in ("all", "activities"):
            print(garmin.ingest_activities(days=args.days))
        if args.what in ("all", "sleep"):
            print(garmin.ingest_sleep(days=min(args.days, 30)))
        if args.what in ("all", "daily"):
            print(garmin.ingest_daily(days=min(args.days, 30)))
        if args.what in ("all", "scheduled"):
            print(garmin.ingest_scheduled_workouts(months_ahead=2))
        if args.what in ("all", "workouts"):
            print(garmin.ingest_workout_details())

    elif args.cmd == "strava-auth":
        from .ingest import strava

        strava.authenticate()

    elif args.cmd == "ingest-strava":
        from .ingest import strava

        print(strava.ingest_activities(days=args.days))

    elif args.cmd == "ingest-fit":
        from .ingest import fit_files

        print(fit_files.ingest_directory())

    elif args.cmd == "ingest-export":
        from .ingest import garmin_export

        if args.what == "all":
            print(garmin_export.ingest_all())
        elif args.what == "activities":
            print(garmin_export.ingest_activities())
        elif args.what == "sleep":
            print(garmin_export.ingest_sleep())
        elif args.what == "daily":
            print(garmin_export.ingest_daily_metrics())
        elif args.what == "vo2max":
            print(garmin_export.ingest_vo2max())
        elif args.what == "predictions":
            print(garmin_export.ingest_race_predictions())
        elif args.what == "menstrual":
            print(garmin_export.ingest_menstrual_cycles())
        elif args.what == "profile":
            print(garmin_export.ingest_user_profile())
        elif args.what == "biometrics":
            print(garmin_export.ingest_biometrics())

    elif args.cmd == "seed-races":
        from .ingest import races_seed

        print(races_seed.seed_races())

    elif args.cmd == "cron-ingest":
        from .ingest import cron_ingest

        return cron_ingest.run(days=args.days)

    elif args.cmd == "ingest-zepp":
        from pathlib import Path

        from .ingest import zepp

        print(zepp.ingest_all(Path(args.path).expanduser()))

    elif args.cmd == "import-mfit":
        from .ingest import mfit

        wmap = None
        if args.weekdays:
            wmap = {}
            for pair in args.weekdays.split(","):
                k, v = pair.split(":")
                wmap[int(k)] = int(v)
        if args.source.startswith("http://") or args.source.startswith("https://"):
            print(mfit.ingest_url(args.source, weekday_map=wmap))
        else:
            print(mfit.ingest_pdf(args.source, weekday_map=wmap))

    elif args.cmd == "serve":
        import uvicorn

        uvicorn.run(
            "garmin_relatorio.api.main:app",
            host=config.api_host,
            port=config.api_port,
            reload=args.reload,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
