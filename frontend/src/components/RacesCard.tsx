import { useEffect, useState } from "react";
import { fetchRaces, formatPace, formatTime, type Race } from "../api/client";

const SPORT_ICON: Record<string, string> = { run: "🏃", swim: "🏊", bike: "🚴", triathlon: "🏆" };
const PHASE_LABEL = { base: "Base", build: "Build", peak: "Peak", taper: "Taper", race_week: "Semana da prova" } as const;
const PHASE_COLOR = {
  base: "#60a5fa",
  build: "#4ade80",
  peak: "#fbbf24",
  taper: "#fb923c",
  race_week: "#ef4444",
} as const;

function formatRaceDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "2-digit" });
}

function distanceLabel(r: Race): string {
  if (r.sport === "triathlon") {
    const s = r.triathlon_swim_m ? `${r.triathlon_swim_m}m` : "?";
    const b = r.triathlon_bike_m ? `${(r.triathlon_bike_m / 1000).toFixed(0)}km` : "?";
    const ru = r.triathlon_run_m ? `${(r.triathlon_run_m / 1000).toFixed(0)}km` : "?";
    return `${s} + ${b} + ${ru}`;
  }
  return r.distance_m ? `${(r.distance_m / 1000).toFixed(r.distance_m % 1000 === 0 ? 0 : 1)}km` : "—";
}

export function RacesCard() {
  const [races, setRaces] = useState<Race[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRaces().then(setRaces).catch((e) => setError(String(e)));
  }, []);

  if (error) return <><h2>Provas alvo</h2><div className="empty">Erro: {error}</div></>;
  if (races.length === 0) return <><h2>Provas alvo</h2><div className="empty">Sem provas cadastradas.</div></>;

  return (
    <>
      <h2>Provas alvo ({races.length})</h2>
      <div className="races">
        {races.map((r) => (
          <div key={r.id} className="race-row">
            <div className="race-head">
              <span style={{ fontSize: 18 }}>{SPORT_ICON[r.sport] || "🏃"}</span>
              <span className="race-name">{r.name}</span>
              <span className="race-countdown">T-{r.days_to}d</span>
            </div>
            <div className="race-meta">
              <span>{formatRaceDate(r.race_date)}</span>
              <span> · {distanceLabel(r)}</span>
              {r.location && <span> · {r.location}</span>}
              {!r.is_confirmed && <span style={{ color: "var(--warn)" }}> · não confirmada</span>}
            </div>
            <div style={{ marginTop: 6 }}>
              <span
                className="zone"
                style={{ background: `${PHASE_COLOR[r.phase]}33`, color: PHASE_COLOR[r.phase] }}
              >
                {PHASE_LABEL[r.phase]}
              </span>
              {r.garmin_prediction && (
                <span className="label" style={{ marginLeft: 8 }}>
                  Predição: {formatTime(r.garmin_prediction.predicted_time_s)} ({formatPace(r.garmin_prediction.predicted_pace_s_km)})
                  {r.garmin_prediction.approximation && " *"}
                </span>
              )}
            </div>
            <p className="recommendation" style={{ marginTop: 6, marginBottom: 0, fontSize: 12 }}>
              {r.phase_message}
            </p>
          </div>
        ))}
      </div>
    </>
  );
}
