"""SQLite schema e helpers. Sem ORM — sqlite3 stdlib basta pra v1."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    id              INTEGER PRIMARY KEY,
    source          TEXT NOT NULL,            -- 'garmin' | 'strava' | 'fit'
    external_id     TEXT NOT NULL,
    sport           TEXT NOT NULL,            -- 'swim'|'bike'|'run'|'yoga'|'strength'|'walking'|'other'
    started_at      TEXT NOT NULL,            -- ISO 8601
    duration_s      INTEGER NOT NULL,
    distance_m      REAL,
    avg_hr          INTEGER,
    max_hr          INTEGER,
    avg_pace_s_km   REAL,                     -- segundos/km (corrida/nado normalizado)
    avg_speed_kmh   REAL,                     -- km/h (bike e walking)
    avg_cadence     REAL,                     -- run: passos/min, bike: rpm, swim: stroke/min
    elevation_gain  REAL,
    calories        INTEGER,
    training_load   REAL,                     -- TRIMP/load se disponivel
    raw             TEXT,                     -- JSON bruto pra debug
    UNIQUE(source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_activities_started_at ON activities(started_at);
CREATE INDEX IF NOT EXISTS idx_activities_sport ON activities(sport);

CREATE TABLE IF NOT EXISTS sleep (
    date            TEXT PRIMARY KEY,         -- YYYY-MM-DD
    total_min       INTEGER,
    deep_min        INTEGER,
    light_min       INTEGER,
    rem_min         INTEGER,
    awake_min       INTEGER,
    score           INTEGER,                  -- Garmin sleep score 0-100
    raw             TEXT
);

CREATE TABLE IF NOT EXISTS daily_metrics (
    date            TEXT PRIMARY KEY,
    resting_hr      INTEGER,
    hrv_overnight   REAL,                     -- ms
    body_battery    INTEGER,                  -- max do dia
    stress_avg      INTEGER,
    steps           INTEGER,
    total_kcal      INTEGER,                  -- gasto total do dia
    active_kcal     INTEGER,                  -- gasto por atividade
    bmr_kcal        INTEGER,                  -- gasto basal (metabolismo de repouso)
    raw             TEXT
);

CREATE TABLE IF NOT EXISTS hr_zones (
    sport           TEXT PRIMARY KEY,         -- 'default' | 'run' | 'bike' | 'swim'
    resting_hr      INTEGER,
    max_hr          INTEGER,
    z1_floor        INTEGER,
    z2_floor        INTEGER,
    z3_floor        INTEGER,
    z4_floor        INTEGER,
    z5_floor        INTEGER,
    method          TEXT,                     -- 'HR_MAX' | 'HRR' | 'LTHR'
    raw             TEXT
);

CREATE TABLE IF NOT EXISTS personal_records (
    pr_id           INTEGER PRIMARY KEY,      -- personalRecordId do Garmin
    activity_id     TEXT,
    record_type     TEXT NOT NULL,            -- "Best 5K", "Most Steps in a Day", etc
    value           REAL NOT NULL,            -- meters/seconds/steps depende do tipo
    achieved_at     TEXT NOT NULL,            -- ISO 8601
    is_current      INTEGER DEFAULT 1,
    raw             TEXT
);

CREATE TABLE IF NOT EXISTS vo2max (
    date            TEXT NOT NULL,
    sport           TEXT NOT NULL,            -- 'run' | 'bike' | 'swim'
    value           REAL NOT NULL,
    raw             TEXT,
    PRIMARY KEY (date, sport)
);

CREATE TABLE IF NOT EXISTS menstrual_cycles (
    start_date          TEXT PRIMARY KEY,         -- YYYY-MM-DD
    predicted_cycle_length  INTEGER,
    predicted_period_length INTEGER,
    actual_cycle_length     INTEGER,
    actual_period_length    INTEGER,
    cycle_type          TEXT,                     -- 'REGULAR' | 'IRREGULAR'
    fertile_window_start    INTEGER,              -- dia do ciclo (1-indexed)
    fertile_window_length   INTEGER,
    status              TEXT,                     -- 'CURRENT' | 'PAST'
    raw                 TEXT
);

CREATE TABLE IF NOT EXISTS menstrual_logs (
    date                TEXT PRIMARY KEY,
    flow                TEXT,                     -- 'LIGHT' | 'MEDIUM' | 'HEAVY' | NULL
    symptoms            TEXT,                     -- JSON array
    moods               TEXT,                     -- JSON array
    ovulation_day       INTEGER DEFAULT 0,
    raw                 TEXT
);

CREATE TABLE IF NOT EXISTS races (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    race_date       TEXT NOT NULL,            -- YYYY-MM-DD
    sport           TEXT NOT NULL,            -- 'run' | 'swim' | 'bike' | 'triathlon'
    distance_m      REAL,                     -- distancia primaria (corrida do tri ou prova solo)
    triathlon_swim_m  REAL,
    triathlon_bike_m  REAL,
    triathlon_run_m   REAL,
    location        TEXT,
    target_time_s   INTEGER,                  -- alvo opcional
    notes           TEXT,
    is_confirmed    INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_races_date ON races(race_date);

CREATE TABLE IF NOT EXISTS race_predictions (
    date            TEXT PRIMARY KEY,
    race_5k_s       INTEGER,
    race_10k_s      INTEGER,
    race_half_s     INTEGER,
    race_marathon_s INTEGER,
    raw             TEXT
);

CREATE TABLE IF NOT EXISTS scheduled_workouts (
    id              INTEGER PRIMARY KEY,       -- calendar item id
    workout_id      INTEGER,                   -- referencia pro workout (pode repetir entre datas)
    title           TEXT NOT NULL,
    scheduled_date  TEXT NOT NULL,             -- YYYY-MM-DD
    sport_type      TEXT,                      -- cycling, running, swimming, etc.
    duration_s      INTEGER,                   -- se conhecido
    distance_m      REAL,
    is_race         INTEGER DEFAULT 0,
    raw             TEXT,
    fetched_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scheduled_date ON scheduled_workouts(scheduled_date);

CREATE TABLE IF NOT EXISTS user_profile (
    user_id         INTEGER PRIMARY KEY,
    birth_date      TEXT,                     -- YYYY-MM-DD
    gender          TEXT,                     -- 'FEMALE' | 'MALE' | 'OTHER'
    locale          TEXT,
    max_hr_override INTEGER,                  -- manual override (ex: 182 do exame de esteira)
    resting_hr_override INTEGER,
    raw             TEXT,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS biometrics (
    date            TEXT NOT NULL PRIMARY KEY,  -- YYYY-MM-DD
    weight_g        INTEGER,                  -- gramas (Garmin armazena assim)
    height_cm       REAL,
    vo2max_running  REAL,
    vo2max_cycling  REAL,
    ftp_watts       INTEGER,
    ftp_auto        INTEGER DEFAULT 0,
    raw             TEXT
);

CREATE TABLE IF NOT EXISTS strength_routines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,            -- 'mfit'
    source_file     TEXT NOT NULL,
    name            TEXT NOT NULL,            -- 'Full body 1' etc
    order_idx       INTEGER NOT NULL,         -- 1, 2 etc (ordem dentro do arquivo)
    weekday         INTEGER,                  -- 0=Seg .. 6=Dom (mapeado por convencao)
    routine_label   TEXT,                     -- 'Avaliação 2'
    fitness_level   TEXT,
    imported_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_file, order_idx)
);

CREATE TABLE IF NOT EXISTS strength_exercises (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    routine_id      INTEGER NOT NULL,
    order_idx       INTEGER NOT NULL,
    name            TEXT NOT NULL,
    sets            TEXT,                     -- '3x20', '1-15+4x10-08'
    load_text       TEXT,                     -- '20kg', 'nenhuma'
    load_kg         REAL,                     -- parsed numerico, NULL pra alongamento
    rest_s          INTEGER,                  -- 60, 30 etc
    rest_text       TEXT,                     -- '60s', '20s'
    instructions    TEXT,
    FOREIGN KEY (routine_id) REFERENCES strength_routines(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_strength_ex_routine ON strength_exercises(routine_id);

CREATE TABLE IF NOT EXISTS workout_details (
    workout_id              INTEGER PRIMARY KEY,
    name                    TEXT,
    sport                   TEXT,
    estimated_duration_s    INTEGER,
    estimated_distance_m    REAL,
    steps_json              TEXT,
    raw                     TEXT,
    fetched_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingest_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    inserted        INTEGER DEFAULT 0,
    updated         INTEGER DEFAULT 0,
    error           TEXT
);
"""


def init_db(path: Path | None = None) -> None:
    target = path or config.db_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as conn:
        conn.executescript(SCHEMA)
        _run_migrations(conn)


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Idempotente: adiciona colunas que CREATE TABLE IF NOT EXISTS nao adiciona em DBs ja existentes."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(activities)").fetchall()}
    if "avg_speed_kmh" not in cols:
        conn.execute("ALTER TABLE activities ADD COLUMN avg_speed_kmh REAL")
    if "avg_cadence" not in cols:
        conn.execute("ALTER TABLE activities ADD COLUMN avg_cadence REAL")
    dm_cols = {row[1] for row in conn.execute("PRAGMA table_info(daily_metrics)").fetchall()}
    for kcal_col in ("total_kcal", "active_kcal", "bmr_kcal"):
        if kcal_col not in dm_cols:
            conn.execute(f"ALTER TABLE daily_metrics ADD COLUMN {kcal_col} INTEGER")


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    target = path or config.db_path
    init_db(target)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
