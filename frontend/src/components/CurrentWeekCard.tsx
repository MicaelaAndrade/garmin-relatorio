import type { CurrentWeek } from "../api/client";

const SPORT_LABEL: Record<string, string> = {
  run: "Corrida",
  bike: "Bike",
  swim: "Nado",
  strength: "Fortalecimento",
  yoga: "Yoga",
  walking: "Caminhada",
  other: "Outros",
};

function fmtShort(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export function CurrentWeekCard({ data }: { data: CurrentWeek }) {
  const range = data.week_end ? `${fmtShort(data.week_start)} → ${fmtShort(data.week_end)}` : null;
  return (
    <>
      <h2>Semana atual</h2>
      {range && (
        <div className="muted" style={{ fontSize: 11, marginTop: -4, marginBottom: 6 }}>
          {range}
        </div>
      )}
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
