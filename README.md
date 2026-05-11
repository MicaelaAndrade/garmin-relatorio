# Garmin Relatório — Triathlon

Dashboard local pra acompanhar evolução em natação, bike e corrida — com **risco de lesão** baseado em ACWR (Acute:Chronic Workload Ratio), métricas de sono/HRV, e predição de tempo de prova via fórmula de Riegel.

Puxa dados de:
- **Garmin Connect** (atividades, sono, FC repouso, HRV, body battery, stress) — via API com login
- **Garmin GDPR Export** (DI_CONNECT) — todo histórico sem precisar logar, **inclui VO2max e race predictions calculadas pelo Garmin**
- **Strava** (atividades — sem dados de sono/HRV)
- **Arquivos `.fit`** baixados manualmente

Stack:
- Backend: Python 3.12 + FastAPI + pandas + SQLite
- Frontend: Vite + React 19 + Recharts

---

## Setup

### 1. Backend

```bash
cd backend
uv sync                # instala deps Python
cp ../.env.example ../.env
# edite .env com suas credenciais Garmin
```

### 2. Frontend

```bash
cd frontend
pnpm install
```

### 3. Garmin GDPR Export (recomendado pra carga inicial)

A API live limita a quantos dias você puxa (e bloqueia logins frequentes). Pra carregar **todo o histórico de uma vez**:

1. Acesse https://www.garmin.com/account/datamanagement/exportdata
2. Solicite "Request Data Export" — Garmin envia email em ~24h com link do ZIP
3. Extraia o ZIP em algum lugar (ex: `~/Documentos/garmin-export/`)
4. Aponte no `.env`:
   ```bash
   GARMIN_EXPORT_DIR=/caminho/para/DI_CONNECT
   ```
5. Rode:
   ```bash
   uv run garmin-relatorio ingest-export
   ```

Esse ingest carrega:
- Todas as atividades (`summarizedActivities.json`)
- Sono completo (chunks de 90 dias)
- Métricas diárias (resting HR, HRV, stress, body battery, steps) via UDS + healthStatusData
- VO2max histórico
- **Race predictions calculadas pelo próprio Garmin** (mais precisas que Riegel — usam VO2max)

### 4. Strava (opcional, se for usar)

1. Acesse https://www.strava.com/settings/api
2. Crie um app: name `garmin-relatorio`, Authorization Callback Domain `localhost`
3. Copie `Client ID` e `Client Secret` para o `.env`
4. Rode:
   ```bash
   cd backend
   uv run garmin-relatorio strava-auth
   ```
   Vai abrir o navegador. Autorize e o token fica salvo em `backend/data/strava_token.json`.

---

## Uso diário

### Puxa dados (rode quando quiser atualizar — recomendo 1x ao dia)

```bash
cd backend

# Garmin: tudo (atividades últimos 90 dias + sono/diário últimos 30)
uv run garmin-relatorio ingest-garmin

# Só atividades, mais histórico
uv run garmin-relatorio ingest-garmin --what activities --days 180

# Strava
uv run garmin-relatorio ingest-strava --days 90

# .fit manuais (coloque arquivos em backend/data/exports/)
uv run garmin-relatorio ingest-fit
```

### Sobe o dashboard

Em dois terminais:

```bash
# Terminal 1 — API
cd backend
uv run garmin-relatorio serve --reload

# Terminal 2 — frontend
cd frontend
pnpm dev
```

Abre em http://localhost:5173

---

## O que o dashboard mostra

| Card | O que é | Pra que serve |
|------|---------|--------------|
| **Semana atual** | sessões, duração e km da semana corrente, separado por modalidade | Sanity check rápido — você está fazendo o volume planejado? |
| **Risco de lesão (ACWR)** | razão carga 7d / carga 28d + zona (ótimo/moderado/alto) | Detecta picos de carga que precedem lesão (Gabbett 2016) |
| **Sono e recuperação** | horas de sono últimas 30 noites + flag de prontidão | Cruza sono curto + HR repouso elevado pra alertar fadiga acumulada |
| **Volume semanal** | gráfico empilhado por modalidade, últimas ~12 semanas | Visualiza progressão e identifica plateaus |
| **Predição (Riegel)** | tempo estimado em 5k/10k/21k/42k baseado nos seus melhores recentes | Estimativa de pace de prova (T2 = T1 × (D2/D1)^1.06) |
| **Predição Garmin** | tempo estimado calculado pelo seu relógio (FirstBeat) | Mais precisa que Riegel — incorpora VO2max trend |
| **Riegel × Garmin** | tabela lado a lado com diferença | Mostra divergência entre fórmula clássica e modelo do Garmin |
| **VO2max** | valor atual + curva 1 ano | Acompanha capacidade aeróbica (sobe = melhora cardiorrespiratória) |
| **Overtraining detector** | score 0-4 baseado em HRV + RHR + sleep score + sono curto | Multi-métrica, detecta fadiga acumulada antes da lesão |
| **Calendário (heatmap)** | grade tipo GitHub colorida por carga TRIMP diária (180 dias) | Visual de consistência e identificação de gaps/picos |
| **Atividades recentes** | últimas 20 com pace, FC, distância | Histórico rápido sem precisar abrir Garmin/Strava |
| **Personal records** | todos os PRs do Garmin ordenados por relevância pra triathlon | Acompanha marcas pessoais |
| **Plano da próxima semana** | sugere sessões por modalidade, distribuição Z1-Z5, sessões-chave e dias de descanso | Combina ACWR, overtraining, fase de prova mais próxima — pega no jeito sem precisar planejar |

---

## Metodologia das métricas-chave

### ACWR (Acute:Chronic Workload Ratio)

- **Carga** = duração (min) × fator zona FC (TRIMP simplificado, calibrado com suas zonas Z1-Z5 reais salvas em `hr_zones`)
- **Aguda** = média móvel 7 dias
- **Crônica** = média móvel 28 dias
- **ACWR** = aguda ÷ crônica

Quando suas zonas reais não estão disponíveis (sem ingest do export GDPR), usa fator estimado por faixas de HR genéricas.

| Zona | Faixa | Significado |
|------|-------|------------|
| Destreino | < 0.8 | Carga baixa demais — perde adaptação |
| Ótimo | 0.8–1.3 | Sweet spot, progresso seguro |
| Moderado | 1.3–1.5 | Cuidado, considere recuperação |
| **Alto** | **> 1.5** | **Risco elevado de lesão** |

Referências: Gabbett TJ. *The training-injury prevention paradox*. BJSM 2016. Hulin BT et al. BJSM 2014.

### Riegel para predição

`T2 = T1 × (D2/D1)^1.06`

Confiança alta quando D2 está dentro de ±20% da distância base. Para extrapolações maiores (ex: usar 5k pra prever maratona), o expoente precisa ajuste — toma como aproximação.

### Readiness

Flag de 3 níveis baseado em:
- Sono médio das últimas 3 noites < 6.5h
- HR repouso últimos 3 dias > baseline + 5 bpm

0 alertas = verde · 1 = amarelo · 2 = vermelho

---

## Estrutura

```
garmin-relatorio/
├── .env                       # credenciais (não comita)
├── .env.example
├── backend/
│   ├── pyproject.toml
│   ├── data/
│   │   ├── garmin.db          # SQLite (gerado)
│   │   ├── strava_token.json  # OAuth (gerado)
│   │   └── exports/           # .fit manuais
│   └── src/garmin_relatorio/
│       ├── config.py          # carrega .env
│       ├── db.py              # schema SQLite
│       ├── cli.py             # entry point
│       ├── ingest/
│       │   ├── garmin.py      # python-garminconnect
│       │   ├── strava.py      # stravalib + OAuth
│       │   └── fit_files.py   # fitparse
│       ├── analysis/
│       │   ├── volume.py      # agregação por sport/semana
│       │   ├── acwr.py        # risco lesão
│       │   ├── recovery.py    # sono + readiness
│       │   └── performance.py # Riegel
│       └── api/main.py        # FastAPI
└── frontend/
    ├── package.json
    └── src/
        ├── App.tsx
        ├── api/client.ts      # tipos + fetch
        └── components/
            ├── CurrentWeekCard.tsx
            ├── VolumeChart.tsx
            ├── InjuryRiskCard.tsx
            ├── SleepCard.tsx
            └── PerformanceCard.tsx
```

---

## Automação do ingest diário

Pra rodar 1x/dia sem clicar nada, tem três opções em `scripts/`:

### Opção A — systemd user timer (recomendado em Linux)

```bash
bash scripts/install-systemd-timer.sh
```

Instala em `~/.config/systemd/user/` e habilita timer pra rodar todo dia 07:00 (com jitter de 30min). Logs em `backend/data/cron.log` + `journalctl --user -u garmin-relatorio-ingest.service`.

### Opção B — crontab

```cron
0 7 * * * $HOME/Documentos/garmin-relatorio/scripts/garmin-relatorio-cron.sh >> $HOME/Documentos/garmin-relatorio/backend/data/cron.log 2>&1
```

### Opção C — manual

```bash
cd backend
uv run garmin-relatorio cron-ingest --days 7
```

O wrapper pula automaticamente fontes sem credencial (Garmin, Strava) e nunca aborta a sequência por uma falha individual. Útil pra ambientes mistos onde só Garmin (ou só Strava) está configurado.

## Roadmap (v1+)

- [x] ~~Tabela de atividades recentes~~ ✓
- [x] ~~Zonas de FC personalizadas~~ ✓ (extraídas do export)
- [x] ~~Detecção de overtraining (HRV + RHR + sleep)~~ ✓
- [x] ~~Calendário visual de carga~~ ✓
- [x] ~~Comparação Riegel × Garmin~~ ✓
- [x] ~~Personal records~~ ✓
- [x] ~~Automatizar ingest com cron (1x/dia)~~ ✓ (systemd timer + crontab)
- [x] ~~Link "abrir no Garmin Connect" em cada atividade da tabela~~ ✓
- [x] ~~Plano semanal sugerido baseado em ACWR~~ ✓
- [x] ~~Cycle phase tracker (dados estão no export)~~ ✓
- [x] ~~Gráfico de pace por modalidade ao longo do tempo~~ ✓ (mensal corrida/bike/nado com cadência)
- [x] ~~Distribuição de tempo nas zonas Z1-Z5 por treino~~ ✓ (barra empilhada por sessão)
- [x] ~~Ingest dos treinos prescritos pelo coach (Treius/Garmin Connect)~~ ✓
- [x] ~~Importar rotina de fortalecimento (PDF MFit Personal)~~ ✓
- [ ] Export PDF do relatório mensal

---

## Avisos

- A lib `python-garminconnect` é **não oficial** (Garmin não publica API pública). Funciona bem mas pode quebrar se Garmin mudar o backend deles.
- Login excessivo no Garmin pode bloquear a conta temporariamente. A lib cacheia sessão em `backend/data/garmin_session/` — não delete.
- O risco de lesão calculado aqui é uma **heurística**, não diagnóstico médico. Se tiver dor, consulta fisio/médico.
