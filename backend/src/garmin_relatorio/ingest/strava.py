"""Ingest do Strava via stravalib + OAuth.

Fluxo:
1. `garmin-relatorio strava-auth` abre URL no browser pra autorizar
2. Salva refresh_token em backend/data/strava_token.json
3. `garmin-relatorio ingest-strava` puxa atividades novas

Strava NAO fornece sono nem HRV — so atividades.
"""
from __future__ import annotations

import json
import logging
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stravalib import Client

from ..config import ROOT, config
from ..db import connect

log = logging.getLogger(__name__)

TOKEN_PATH = ROOT / "backend" / "data" / "strava_token.json"
REDIRECT_URI = "http://localhost:8765/callback"

SPORT_MAP = {
    "Run": "run",
    "TrailRun": "run",
    "VirtualRun": "run",
    "Ride": "bike",
    "VirtualRide": "bike",
    "MountainBikeRide": "bike",
    "GravelRide": "bike",
    "EBikeRide": "bike",
    "EMountainBikeRide": "bike",
    "Swim": "swim",
    "Yoga": "yoga",
    "Pilates": "yoga",
    "WeightTraining": "strength",
    "Crossfit": "strength",
    "Workout": "strength",
    "Walk": "walking",
    "Hike": "walking",
}


def _save_token(token: dict) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(token, indent=2))


def _load_token() -> dict | None:
    if not TOKEN_PATH.exists():
        return None
    return json.loads(TOKEN_PATH.read_text())


def authenticate() -> None:
    """Roda o fluxo OAuth uma unica vez. Abre browser, escuta callback local."""
    import http.server
    import socketserver
    import urllib.parse

    if not config.strava_client_id or not config.strava_client_secret:
        raise RuntimeError(
            "Configure STRAVA_CLIENT_ID e STRAVA_CLIENT_SECRET no .env. "
            "Crie o app em https://www.strava.com/settings/api"
        )

    client = Client()
    auth_url = client.authorization_url(
        client_id=config.strava_client_id,
        redirect_uri=REDIRECT_URI,
        scope=["read", "activity:read_all"],
    )
    print(f"Abrindo navegador para autorizar:\n{auth_url}")
    webbrowser.open(auth_url)

    received_code: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            if "code" in params:
                received_code["code"] = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>OK! Pode fechar.</h1>")
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, *args):  # silencia logs do http server
            pass

    with socketserver.TCPServer(("localhost", 8765), Handler) as httpd:
        while "code" not in received_code:
            httpd.handle_request()

    token = client.exchange_code_for_token(
        client_id=config.strava_client_id,
        client_secret=config.strava_client_secret,
        code=received_code["code"],
    )
    _save_token(token)
    print(f"Token salvo em {TOKEN_PATH}")


def _client() -> Client:
    token = _load_token()
    if not token:
        raise RuntimeError("Sem token. Rode primeiro: garmin-relatorio strava-auth")

    if token["expires_at"] < time.time():
        client = Client()
        new_token = client.refresh_access_token(
            client_id=config.strava_client_id,
            client_secret=config.strava_client_secret,
            refresh_token=token["refresh_token"],
        )
        _save_token(new_token)
        token = new_token

    return Client(access_token=token["access_token"])


def ingest_activities(days: int = 90) -> dict[str, int]:
    client = _client()
    after = datetime.now(timezone.utc) - timedelta(days=days)
    inserted = updated = 0

    with connect() as conn:
        for act in client.get_activities(after=after):
            sport = SPORT_MAP.get(str(act.sport_type), "other")
            duration = int(act.elapsed_time.total_seconds()) if act.elapsed_time else 0
            distance = float(act.distance) if act.distance else None
            pace = (duration / (distance / 1000.0)) if distance and sport not in ("bike", "walking") else None
            speed_kmh = None
            if sport in ("bike", "walking") and getattr(act, "average_speed", None):
                # Strava reporta average_speed em m/s
                speed_kmh = round(float(act.average_speed) * 3.6, 2)
            cadence = None
            if getattr(act, "average_cadence", None):
                # Strava: passos/min ÷ 2 pra corrida (reporta cadencia por perna)
                cad = float(act.average_cadence)
                cadence = round(cad * 2.0, 1) if sport == "run" else round(cad, 1)

            cur = conn.execute(
                """
                INSERT INTO activities (
                    source, external_id, sport, started_at, duration_s, distance_m,
                    avg_hr, max_hr, avg_pace_s_km, avg_speed_kmh, avg_cadence,
                    elevation_gain, calories, training_load, raw
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    sport=excluded.sport,
                    duration_s=excluded.duration_s,
                    distance_m=excluded.distance_m,
                    avg_hr=excluded.avg_hr,
                    max_hr=excluded.max_hr,
                    avg_pace_s_km=excluded.avg_pace_s_km,
                    avg_speed_kmh=excluded.avg_speed_kmh,
                    avg_cadence=excluded.avg_cadence
                """,
                (
                    "strava",
                    str(act.id),
                    sport,
                    act.start_date.isoformat(),
                    duration,
                    distance,
                    int(act.average_heartrate) if act.average_heartrate else None,
                    int(act.max_heartrate) if act.max_heartrate else None,
                    pace,
                    speed_kmh,
                    cadence,
                    float(act.total_elevation_gain) if act.total_elevation_gain else None,
                    int(act.kilojoules) if act.kilojoules else None,
                    None,
                    json.dumps(act.model_dump(mode="json"), default=str),
                ),
            )
            if cur.rowcount == 1:
                inserted += 1
            else:
                updated += 1

    log.info("Strava: %d inseridas, %d atualizadas", inserted, updated)
    return {"inserted": inserted, "updated": updated}
