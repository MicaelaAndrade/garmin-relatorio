import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PaceEvolution, PaceMonth } from "../api/client";

function paceMin(secPerKm: number | undefined): number | null {
  return secPerKm ? +(secPerKm / 60).toFixed(2) : null;
}

function paceFormatter(v: number): string {
  return `${Math.floor(v)}:${String(Math.round((v % 1) * 60)).padStart(2, "0")}/km`;
}

function buildRows(months: PaceMonth[], kind: "pace" | "speed") {
  return months
    .map((m) => {
      const value = kind === "pace" ? paceMin(m.avg_pace_s_km) : (m.avg_speed_kmh ?? null);
      if (value == null) return null;
      return { month: m.month.slice(0, 7), value, cadence: m.avg_cadence };
    })
    .filter(Boolean) as { month: string; value: number; cadence: number | null }[];
}

function PaceChart({
  title,
  color,
  rows,
  kind,
  unit,
  reversed,
}: {
  title: string;
  color: string;
  rows: { month: string; value: number; cadence: number | null }[];
  kind: "pace" | "speed";
  unit: string;
  reversed: boolean;
}) {
  const last = rows[rows.length - 1];
  const first = rows[0];
  const delta = last && first ? last.value - first.value : null;
  const deltaPositive = kind === "pace" ? (delta != null && delta < 0) : (delta != null && delta > 0);
  const cadenceAvg = (() => {
    const vals = rows.map((r) => r.cadence).filter((v): v is number => v != null);
    return vals.length ? Math.round((vals.reduce((s, v) => s + v, 0) / vals.length) * 10) / 10 : null;
  })();

  return (
    <div className="pace-block">
      <div className="pace-block-head">
        <span style={{ color, fontWeight: 600, fontSize: 12 }}>{title}</span>
        {delta != null && (
          <span
            className="pace-delta"
            style={{ color: deltaPositive ? "var(--accent)" : "var(--muted)" }}
          >
            {kind === "pace"
              ? `${delta > 0 ? "+" : ""}${Math.abs(delta * 60).toFixed(0)}s/km no período`
              : `${delta > 0 ? "+" : ""}${delta.toFixed(2)} ${unit} no período`}
          </span>
        )}
        {cadenceAvg != null && (
          <span className="pace-cadence">cad ~{cadenceAvg}</span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={100}>
        <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
          <XAxis dataKey="month" stroke="#8b96a8" fontSize={10} />
          <YAxis
            stroke="#8b96a8"
            fontSize={10}
            domain={kind === "pace" ? ["dataMin - 0.3", "dataMax + 0.3"] : ["dataMin - 1", "dataMax + 1"]}
            reversed={reversed}
          />
          <Tooltip
            contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
            formatter={(v: number) => (kind === "pace" ? paceFormatter(v) : `${v.toFixed(2)} ${unit}`)}
          />
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function PaceEvolutionCard({ data }: { data: PaceEvolution }) {
  const runRows = buildRows(data.run, "pace");
  const swimRows = buildRows(data.swim, "pace");
  const bikeRows = buildRows(data.bike, "speed");

  if (runRows.length === 0 && swimRows.length === 0 && bikeRows.length === 0) {
    return (
      <>
        <h2>Evolução de pace</h2>
        <div className="empty">Sem dados suficientes.</div>
      </>
    );
  }

  return (
    <>
      <h2>Evolução de pace & velocidade</h2>
      <div className="label" style={{ marginBottom: 12 }}>
        Médias mensais ponderadas — corrida e nado em min/km (↓ melhor), bike em km/h (↑ melhor)
      </div>
      {runRows.length > 1 && (
        <PaceChart title="Corrida" color="#4ade80" rows={runRows} kind="pace" unit="min/km" reversed />
      )}
      {bikeRows.length > 1 && (
        <PaceChart title="Bike" color="#60a5fa" rows={bikeRows} kind="speed" unit="km/h" reversed={false} />
      )}
      {swimRows.length > 1 && (
        <PaceChart title="Nado" color="#fbbf24" rows={swimRows} kind="pace" unit="min/km" reversed />
      )}
    </>
  );
}
