import type { GarminPredictionPoint, GarminPredictions } from "../api/client";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatPace, formatTime } from "../api/client";

export function GarminPredictionsCard({
  current,
  series,
}: {
  current: GarminPredictions;
  series: GarminPredictionPoint[];
}) {
  if (current.predictions.length === 0) {
    return (
      <>
        <h2>Predição Garmin (corrida)</h2>
        <div className="empty">Sem predições no histórico.</div>
      </>
    );
  }

  // converte para minutos pra ficar legivel no eixo Y
  const chartData = series.map((p) => ({
    date: p.date,
    "5K": p.race_5k_s ? Math.round(p.race_5k_s / 60) : null,
    "10K": p.race_10k_s ? Math.round(p.race_10k_s / 60) : null,
    "21K": p.race_half_s ? Math.round(p.race_half_s / 60) : null,
  }));

  return (
    <>
      <h2>Predição Garmin (corrida)</h2>
      <div className="label" style={{ marginBottom: 8 }}>
        Calculada pelo seu relógio · Atualizada {current.date}
      </div>
      <div className="predictions" style={{ marginBottom: 12 }}>
        {current.predictions.map((p) => (
          <div key={p.distance_m} className="pred-row">
            <span>{p.label}</span>
            <span>
              {formatTime(p.predicted_time_s)}{" "}
              <span className="label">({formatPace(p.predicted_pace_s_km)})</span>
            </span>
            <span></span>
          </div>
        ))}
      </div>
      {series.length > 1 && (
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={chartData} margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
            <XAxis dataKey="date" stroke="#8b96a8" fontSize={10} tickFormatter={(d) => d.slice(2, 7)} />
            <YAxis stroke="#8b96a8" fontSize={10} unit="m" />
            <Tooltip
              contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
              formatter={(v) => `${v} min`}
            />
            <Line type="monotone" dataKey="5K" stroke="#4ade80" strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="10K" stroke="#60a5fa" strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="21K" stroke="#fbbf24" strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </>
  );
}
