"""Carrega config do .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

# Re-exporta REQUESTS_CA_BUNDLE pro environ pra requests/httpx pegarem
# (necessario quando atras de proxy SSL corporativo tipo Netskope)
_ca_bundle = os.getenv("REQUESTS_CA_BUNDLE", "").strip()
if _ca_bundle and Path(_ca_bundle).exists():
    os.environ["REQUESTS_CA_BUNDLE"] = _ca_bundle
    os.environ["SSL_CERT_FILE"] = _ca_bundle


@dataclass(frozen=True)
class Config:
    garmin_email: str
    garmin_password: str
    strava_client_id: str
    strava_client_secret: str
    api_host: str
    api_port: int
    db_path: Path
    garmin_export_dir: Path | None  # diretorio do GDPR export (DI_CONNECT)
    anthropic_api_key: str

    @classmethod
    def load(cls) -> "Config":
        db_relative = os.getenv("DB_PATH", "backend/data/garmin.db")
        db_path = (ROOT / db_relative).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        export_raw = os.getenv("GARMIN_EXPORT_DIR", "").strip()
        export_dir = Path(export_raw).expanduser().resolve() if export_raw else None

        return cls(
            garmin_email=os.getenv("GARMIN_EMAIL", ""),
            garmin_password=os.getenv("GARMIN_PASSWORD", ""),
            strava_client_id=os.getenv("STRAVA_CLIENT_ID", ""),
            strava_client_secret=os.getenv("STRAVA_CLIENT_SECRET", ""),
            api_host=os.getenv("API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("API_PORT", "8000")),
            db_path=db_path,
            garmin_export_dir=export_dir,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        )


config = Config.load()
