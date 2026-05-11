import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PaceEvolution, PaceMonth } from "../api/client";

type ChartKind = "pace_km" | "pace_100m" | "speed_kmh";

function paceMin(secPerKm: number | undefined): number | null {
  return secPerKm ? +(secPerKm / 60).toFixed(2) : null;
}

function paceMin100m(secPerKm: number | undefined): number | null {
  // 100m = 1/10 km → segundos por 100m = pace_s_km / 10
  return secPerKm ? +(secPerKm / 10 / 60).toFixed(2) : null;
}

function formatPace(v: number, unit: "km" | "100m"): string {
  const m = Math.floor(v);
  const s = Math.round((v % 1) * 60);
  return `${m}:${String(s).padStart(2, "0")}/${unit}`;
}

function buildRows(months: PaceMonth[], kind: ChartKind) {
  return months
    .map((m) => {
      let value: number | null = null;
      if (kind === "pace_km") value = paceMin(m.avg_pace_s_km);
      else if (kind === "pace_100m") value = paceMin100m(m.avg_pace_s_km);
      else value = m.avg_speed_kmh ?? null;
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
  cadenceUnit,
  extraHeader,
}: {
  title: string;
  color: string;
  rows: { month: string; value: number; cadence: number | null }[];
  kind: ChartKind;
  cadenceUnit?: string;
  extraHeader?: string;
}) {
  const last = rows[rows.length - 1];
  const first = rows[0];
  const delta = last && first ? last.value - first.value : null;
  // Pra pace, menor é melhor; pra velocidade, maior é melhor
  const isPace = kind !== "speed_kmh";
  const reversed = isPace;
  const deltaPositive = isPace ? (delta != null && delta < 0) : (delta != null && delta > 0);

  const cadenceAvg = (() => {
    const vals = rows.map((r) => r.cadence).filter((v): v is number => v != null);
    return vals.length ? Math.round((vals.reduce((s, v) => s + v, 0) / vals.length) * 10) / 10 : null;
  })();

  const deltaText = (() => {
    if (delta == null) return null;
    const sign = delta > 0 ? "+" : "";
    if (kind === "pace_km") return `${sign}${Math.abs(delta * 60).toFixed(0)}s/km no período`;
    if (kind === "pace_100m") return `${sign}${Math.abs(delta * 60).toFixed(0)}s/100m no período`;
    return `${sign}${delta.toFixed(2)} km/h no período`;
  })();

  const formatValue = (v: number) => {
    if (kind === "pace_km") return formatPace(v, "km");
    if (kind === "pace_100m") return formatPace(v, "100m");
    return `${v.toFixed(2)} km/h`;
  };

  return (
    <div className="pace-block">
      <div className="pace-block-head">
        <span style={{ color, fontWeight: 600, fontSize: 12 }}>{title}</span>
        {last && (
          <span className="pace-current" style={{ color }} title="Valor mais recente">
            {formatValue(last.value)}
          </span>
        )}
        {extraHeader && <span className="muted" style={{ fontSize: 10 }}>{extraHeader}</span>}
        {deltaText && (
          <span
            className="pace-delta"
            style={{ color: deltaPositive ? "var(--accent)" : "var(--muted)" }}
          >
            {deltaText}
          </span>
        )}
        {cadenceAvg != null && (
          <span className="pace-cadence">
            cad ~{cadenceAvg}
            {cadenceUnit ? ` ${cadenceUnit}` : ""}
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={100}>
        <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
          <XAxis dataKey="month" stroke="#8b96a8" fontSize={10} />
          <YAxis
            stroke="#8b96a8"
            fontSize={10}
            domain={isPace ? ["dataMin - 0.3", "dataMax + 0.3"] : ["dataMin - 1", "dataMax + 1"]}
            reversed={reversed}
            width={36}
          />
          <Tooltip
            contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
            formatter={(v: number) => formatValue(v)}
          />
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function PaceEvolutionCard({ data }: { data: PaceEvolution }) {
  const runRows = buildRows(data.run, "pace_km");
  // Bike: velocidade principal + pace equivalente como anotação
  const bikeRows = buildRows(data.bike, "speed_kmh");
  const swimRows = buildRows(data.swim, "pace_100m");

  // Pace bike (60/km/h) último valor pra mostrar no header como referência
  const lastBikeSpeed = bikeRows[bikeRows.length - 1]?.value;
  const bikeLastPace =
    lastBikeSpeed && lastBikeSpeed > 0
      ? `≈ ${formatPace(60 / lastBikeSpeed, "km")}`
      : undefined;

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
        Médias mensais ponderadas pelo volume — pace ↓ melhor, velocidade ↑ melhor
      </div>
      {runRows.length > 1 && (
        <PaceChart
          title="🏃 Corrida"
          color="#4ade80"
          rows={runRows}
          kind="pace_km"
          cadenceUnit="ppm"
        />
      )}
      {bikeRows.length > 1 && (
        <PaceChart
          title="🚴 Bike"
          color="#60a5fa"
          rows={bikeRows}
          kind="speed_kmh"
          cadenceUnit="rpm"
          extraHeader={bikeLastPace}
        />
      )}
      {swimRows.length > 1 && (
        <PaceChart
          title="🏊 Nado"
          color="#fbbf24"
          rows={swimRows}
          kind="pace_100m"
          cadenceUnit="braçadas/min"
        />
      )}
    </>
  );
}
