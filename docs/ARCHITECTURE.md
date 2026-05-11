# Arquitetura

## Fluxo de dados

```
[Garmin Connect API]      [Strava OAuth API]      [Arquivos .fit locais]
        |                          |                         |
        v                          v                         v
 ingest/garmin.py         ingest/strava.py          ingest/fit_files.py
        \_________________________|_________________________/
                                  |
                                  v
                        SQLite (backend/data/garmin.db)
                        ├── activities  (treinos)
                        ├── sleep       (sono diário)
                        └── daily_metrics (RHR, HRV, BB, stress, passos)
                                  |
                                  v
                          analysis/{volume, acwr, recovery, performance}.py
                                  |
                                  v
                          FastAPI (api/main.py)
                                  |
                          GET /api/dashboard (JSON)
                                  |
                                  v
                            React + Recharts
```

## Decisões

### Por que SQLite?
- Zero setup, arquivo único, basta pra <1 milhão de linhas (anos de treino).
- Se um dia precisar de mais, troca por Postgres mudando só `db.py`.

### Por que sqlite3 stdlib em vez de SQLAlchemy?
- v1 tem 3 tabelas e queries simples. ORM seria overhead.
- Quando crescer, migra pra SQLAlchemy ou SQLModel.

### Por que pandas?
- Rolling windows (ACWR 7d/28d) ficam triviais com `.rolling()`.
- Aceitável: ingest já é I/O bound, processamento não é gargalo.

### Por que separar backend e frontend?
- Permite trocar frontend (mobile, terminal, PDF) sem mexer no core.
- Permite rodar análises por CLI sem subir API (`python -m garmin_relatorio.analysis.acwr`).

### Por que Recharts e não Plotly/Chart.js?
- Recharts é declarativo (componentes React), boa DX.
- Plotly tem mais features mas bundle 5x maior.

## Modelo de dados

```sql
-- activities: 1 linha por treino, dedup por (source, external_id)
-- sleep: 1 linha por noite (date é PK)
-- daily_metrics: 1 linha por dia (date é PK)
```

Atividades duplicadas entre Garmin e Strava? Sim, ambos podem ter o mesmo treino. Para v1 não é problema (filtra por `source` no front se quiser). v2 pode adicionar deduplicação por timestamp + duração.
