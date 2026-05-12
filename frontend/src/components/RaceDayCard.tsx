import { useEffect, useState } from "react";
import { fetchRaces, formatPace, type Race } from "../api/client";

const SPORT_ICON: Record<string, string> = { run: "🏃", swim: "🏊", bike: "🚴", triathlon: "🏆" };
const PHASE_LABEL = {
  base: "Base",
  build: "Build",
  peak: "Peak",
  taper: "Taper",
  race_week: "Semana da prova",
} as const;
const PHASE_COLOR = {
  base: "#60a5fa",
  build: "#4ade80",
  peak: "#fbbf24",
  taper: "#fb923c",
  race_week: "#ef4444",
} as const;

function fmtTime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.round(s % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function formatRaceDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "short", year: "2-digit" });
}

function RacePanel({ race }: { race: Race }) {
  if (race.sport === "triathlon") {
    return (
      <div className="raceday-card">
        <div className="raceday-head">
          <span style={{ fontSize: 22 }}>{SPORT_ICON[race.sport]}</span>
          <h3 style={{ margin: 0, fontSize: 16 }}>{race.name}</h3>
          <span className="race-countdown">T-{race.days_to}d</span>
        </div>
        <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
          {formatRaceDate(race.race_date)} · {race.location || "—"}
        </div>
        <div className="empty">Triathlon — fueling sob medida ainda não implementado.</div>
      </div>
    );
  }

  const dist = race.distance_m;
  const distLabel = dist ? `${(dist / 1000).toFixed(dist % 1000 === 0 ? 0 : 1)}km` : "—";
  const f = race.fueling;
  const g = race.garmin_prediction;
  const r = race.riegel_prediction;

  return (
    <div className="raceday-card">
      <div className="raceday-head">
        <span style={{ fontSize: 22 }}>{SPORT_ICON[race.sport] || "🏃"}</span>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>{race.name}</h3>
          <div className="muted" style={{ fontSize: 11 }}>
            {formatRaceDate(race.race_date)} · {distLabel} · {race.location || "—"}
          </div>
        </div>
        <span
          className="zone"
          style={{ background: `${PHASE_COLOR[race.phase]}33`, color: PHASE_COLOR[race.phase] }}
        >
          {PHASE_LABEL[race.phase]}
        </span>
        <span className="race-countdown">T-{race.days_to}d</span>
      </div>

      <p className="recommendation" style={{ fontSize: 12, margin: "8px 0" }}>{race.phase_message}</p>

      {race.readiness && (
        <div className="readiness-box">
          <div className="readiness-head">
            <span className="readiness-label">Race Readiness</span>
            <span
              className="readiness-score"
              style={{
                color:
                  race.readiness.status === "pronta"
                    ? "var(--accent)"
                    : race.readiness.status === "boa"
                    ? "var(--info)"
                    : race.readiness.status === "regular"
                    ? "var(--warn)"
                    : "var(--danger)",
              }}
            >
              {race.readiness.score}/100
            </span>
            <span className="readiness-status">{race.readiness.status_message}</span>
          </div>
          <div className="readiness-components">
            {race.readiness.components.map((c) => (
              <div key={c.name} className="readiness-component">
                <span className="readiness-comp-name">{c.name}</span>
                <span
                  className="readiness-comp-score"
                  style={{
                    color:
                      c.score >= 85
                        ? "var(--accent)"
                        : c.score >= 65
                        ? "var(--info)"
                        : c.score >= 45
                        ? "var(--warn)"
                        : "var(--danger)",
                  }}
                >
                  {c.score}
                </span>
                <span className="readiness-comp-weight">×{c.weight}%</span>
                <span className="readiness-comp-value muted">{c.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="raceday-preds">
        {g && (
          <div className="raceday-pred">
            <span className="raceday-pred-label">Predição Garmin (VO2max)</span>
            <span className="raceday-pred-value">{fmtTime(g.predicted_time_s)}</span>
            <span className="raceday-pred-sub">
              {formatPace(g.predicted_pace_s_km)}
              {g.scaled_via_riegel ? " · escalado de " + g.based_on_label : g.approximation ? " ~" : ""}
            </span>
          </div>
        )}
        {r && (
          <div className="raceday-pred">
            <span className="raceday-pred-label">Predição Riegel (treino recente)</span>
            <span className="raceday-pred-value">{fmtTime(r.predicted_time_s)}</span>
            <span className="raceday-pred-sub">
              {formatPace(r.predicted_pace_s_km)}
              {r.confidence ? ` · conf. ${r.confidence}` : ""}
            </span>
          </div>
        )}
        {!g && !r && (
          <div className="muted" style={{ fontSize: 12 }}>Sem predições disponíveis.</div>
        )}
      </div>

      {f && (
        <div className="raceday-fuel">
          <div className="raceday-fuel-head">
            🥤 Fueling & estratégia · duração estimada{" "}
            <strong>{f.estimated_duration_label}</strong>
            <span className="muted" style={{ marginLeft: 6, fontSize: 11 }}>
              ({f.prediction_source})
            </span>
          </div>
          <div className="raceday-fuel-grid">
            <div className="raceday-fuel-stat" title="Bebida: 500-750ml/h em clima moderado. Comece nos primeiros 15-20 min, mesmo sem sede.">
              <span className="cal-stat-label">Hidratação</span>
              <span className="cal-stat-value" style={{ color: "var(--info)" }}>{f.fluid_total_ml}</span>
              <span className="cal-stat-unit">ml total · {f.fluid_ml_per_h} ml/h</span>
            </div>
            <div className="raceday-fuel-stat" title="Carbo é seu combustível. Acima de 60min, vai precisar repor. Acima de 2h30, dobra dose.">
              <span className="cal-stat-label">Carbo</span>
              <span className="cal-stat-value" style={{ color: "var(--warn)" }}>{f.carbs_total_g}</span>
              <span className="cal-stat-unit">g total · {f.carbs_g_per_h} g/h</span>
            </div>
            <div className="raceday-fuel-stat" title="Sódio combate hiponatremia em provas longas.">
              <span className="cal-stat-label">Sódio</span>
              <span className="cal-stat-value">{f.sodium_mg_per_h}</span>
              <span className="cal-stat-unit">mg/h</span>
            </div>
            {f.pace_alvo_s_km && (
              <div className="raceday-fuel-stat">
                <span className="cal-stat-label">Pace alvo</span>
                <span className="cal-stat-value" style={{ color: "var(--accent)" }}>{formatPace(f.pace_alvo_s_km)}</span>
                <span className="cal-stat-unit">média</span>
              </div>
            )}
          </div>

          <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>{f.carbs_message}</div>

          {f.splits.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="label" style={{ marginBottom: 4 }}>Splits cumulativos (alvo)</div>
              <div className="raceday-splits">
                {f.splits.map((sp) => (
                  <div key={sp.km} className="raceday-split">
                    <span className="raceday-split-km">{sp.km}km</span>
                    <span className="raceday-split-time">{fmtTime(sp.cumulative_s)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function RaceDayCard() {
  const [races, setRaces] = useState<Race[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRaces()
      .then(setRaces)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return <><h2>Race day</h2><div className="empty">Erro: {error}</div></>;
  }
  if (races.length === 0) {
    return <><h2>Race day</h2><div className="empty">Nenhuma prova futura.</div></>;
  }

  // Prova mais próxima primeiro (já vem ordenada por data)
  const upcoming = races.slice(0, 3);

  return (
    <>
      <h2>Race day toolkit ({races.length} {races.length === 1 ? "prova futura" : "provas futuras"})</h2>
      <div className="muted" style={{ fontSize: 11, marginBottom: 12 }}>
        Predições, pace alvo, hidratação e nutrição. Top 3 próximas mostradas em detalhe.
      </div>
      <div className="raceday-list">
        {upcoming.map((r) => (
          <RacePanel key={r.id} race={r} />
        ))}
      </div>
    </>
  );
}
