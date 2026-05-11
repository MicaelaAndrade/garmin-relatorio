import type { CurrentWeek } from "../api/client";

const SPORT_LABEL: Record<string, string> = { run: "Corrida", bike: "Bike", swim: "Nado", other: "Outros" };

export function CurrentWeekCard({ data }: { data: CurrentWeek }) {
  return (
    <>
      <h2>Semana atual</h2>
      <div className="big">{data.sessions}</div>
      <div className="label">treinos · {data.duration_min.toFixed(0)} min · {data.distance_km.toFixed(1)} km</div>
      <div style={{ marginTop: 16 }}>
        {Object.entries(data.by_sport).map(([sport, s]) => (
          <div key={sport} className="sport-row">
            <span className="sport">{SPORT_LABEL[sport] || sport}</span>
            <span className="stats">{s.sessions}× · {s.distance_km.toFixed(1)}km · {s.duration_min.toFixed(0)}min</span>
          </div>
        ))}
      </div>
    </>
  );
}
