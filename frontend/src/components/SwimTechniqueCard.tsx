import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SwimTechniqueProgress, SwimTechniqueTrend } from "../api/client";

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function fmtPaceFromS100m(s: number | null): string {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}/100m`;
}

function trendArrow(t: SwimTechniqueTrend | undefined): string {
  if (!t || !t.improvement) return "";
  if (t.improvement === "up") return "↑";
  if (t.improvement === "down") return "↓";
  return "→";
}

function trendColor(t: SwimTechniqueTrend | undefined): string {
  if (!t || !t.improvement) return "var(--muted)";
  if (t.improvement === "up") return "var(--good, #4ade80)";
  if (t.improvement === "down") return "var(--danger, #ef4444)";
  return "var(--muted)";
}

type MetricKey = "dps" | "swolf" | "cadence" | "pace_pure_s_100m";
const METRICS: { key: MetricKey; label: string; unit: string; color: string }[] = [
  { key: "dps", label: "DPS", unit: "m/braçada", color: "#4ade80" },
  { key: "swolf", label: "SWOLF", unit: "", color: "#fbbf24" },
  { key: "cadence", label: "Cadência", unit: "strokes/min", color: "#60a5fa" },
  { key: "pace_pure_s_100m", label: "Pace puro", unit: "/100m", color: "#a78bfa" },
];

export function SwimTechniqueCard({ data }: { data: SwimTechniqueProgress }) {
  const [activeMetric, setActiveMetric] = useState<MetricKey>("dps");

  if (!data.available || !data.sessions || data.sessions.length === 0) {
    return (
      <>
        <h2>Evolução técnica · Natação</h2>
        <div className="empty">Sem natações registradas ainda.</div>
      </>
    );
  }

  const chartData = data.sessions.map((s) => ({
    date: shortDate(s.date),
    dps: s.dps,
    swolf: s.swolf,
    cadence: s.cadence,
    pace_pure_s_100m: s.pace_pure_s_100m,
    distance_m: s.distance_m,
  }));

  const metric = METRICS.find((m) => m.key === activeMetric)!;
  const target = data.targets[
    metric.key === "pace_pure_s_100m" ? "pace_s_100m" : metric.key
  ];
  const latest = data.latest;

  const valuesForY = chartData.map((d) => d[metric.key]).filter((v): v is number => v != null);
  const yMin = valuesForY.length ? Math.min(...valuesForY, target) : 0;
  const yMax = valuesForY.length ? Math.max(...valuesForY, target) : 1;
  const pad = (yMax - yMin) * 0.1 || 0.5;

  function fmtY(v: number | null | undefined): string {
    if (v == null) return "—";
    if (metric.key === "pace_pure_s_100m") return fmtPaceFromS100m(v);
    if (metric.key === "dps") return `${v.toFixed(2)} ${metric.unit}`;
    if (metric.key === "swolf") return String(Math.round(v));
    return `${Math.round(v)} ${metric.unit}`;
  }

  return (
    <>
      <h2>Evolução técnica · Natação</h2>
      <div className="muted" style={{ fontSize: 11, marginBottom: 10 }}>
        Últimas {data.count} sessões · linha tracejada = alvo intermediário (triatleta amadora, piscina 25m)
      </div>

      <div className="swim-metric-tabs" style={{ marginBottom: 10 }}>
        {METRICS.map((m) => {
          const tr = data.trends?.[m.key];
          return (
            <button
              key={m.key}
              type="button"
              className={`swim-metric-tab${m.key === activeMetric ? " active" : ""}`}
              onClick={() => setActiveMetric(m.key)}
            >
              <span className="swim-metric-tab-label">{m.label}</span>
              <span className="swim-metric-tab-value" style={{ color: m.color }}>
                {m.key === "pace_pure_s_100m"
                  ? fmtPaceFromS100m(tr?.current ?? null)
                  : tr?.current != null
                    ? m.key === "dps"
                      ? tr.current.toFixed(2)
                      : Math.round(tr.current)
                    : "—"}
              </span>
              <span className="swim-metric-tab-delta" style={{ color: trendColor(tr) }}>
                {trendArrow(tr)} {tr?.delta != null
                  ? m.key === "pace_pure_s_100m"
                    ? `${tr.delta > 0 ? "+" : ""}${tr.delta.toFixed(0)}s`
                    : m.key === "dps"
                      ? `${tr.delta > 0 ? "+" : ""}${tr.delta.toFixed(2)}`
                      : `${tr.delta > 0 ? "+" : ""}${tr.delta.toFixed(1)}`
                  : ""}
              </span>
            </button>
          );
        })}
      </div>

      <div style={{ width: "100%", height: 220 }}>
        <ResponsiveContainer>
          <LineChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--muted)" }} />
            <YAxis
              domain={[yMin - pad, yMax + pad]}
              tick={{ fontSize: 10, fill: "var(--muted)" }}
              tickFormatter={(v) => (metric.key === "pace_pure_s_100m" ? fmtPaceFromS100m(v) : String(v))}
              reversed={metric.key === "swolf" || metric.key === "pace_pure_s_100m"}
            />
            <Tooltip
              contentStyle={{
                background: "var(--card-bg, #1a1f2b)",
                border: "1px solid var(--border, #2a3242)",
                fontSize: 12,
              }}
              formatter={(v: number) => fmtY(v)}
            />
            <ReferenceLine
              y={target}
              stroke={metric.color}
              strokeDasharray="4 4"
              strokeOpacity={0.5}
              label={{
                value: `alvo ${metric.key === "pace_pure_s_100m" ? fmtPaceFromS100m(target) : target}`,
                fill: "var(--muted)",
                fontSize: 10,
                position: "insideTopRight",
              }}
            />
            <Line
              type="monotone"
              dataKey={metric.key}
              stroke={metric.color}
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {latest && (
        <div className="swim-latest-summary">
          <div className="swim-latest-head">
            Última sessão · {shortDate(latest.date)} · {latest.distance_m}m em {latest.duration_min}min
          </div>
          <div className="swim-latest-grid">
            <div className="swim-latest-stat">
              <span className="cal-stat-label">DPS</span>
              <span className="cal-stat-value">{latest.dps?.toFixed(2) ?? "—"}</span>
              <span className="cal-stat-unit">m/braçada</span>
            </div>
            <div className="swim-latest-stat">
              <span className="cal-stat-label">SWOLF</span>
              <span className="cal-stat-value">{latest.swolf ?? "—"}</span>
              <span className="cal-stat-unit">alvo ≤ {data.targets.swolf}</span>
            </div>
            <div className="swim-latest-stat">
              <span className="cal-stat-label">Cadência</span>
              <span className="cal-stat-value">{latest.cadence ?? "—"}</span>
              <span className="cal-stat-unit">strokes/min</span>
            </div>
            <div className="swim-latest-stat">
              <span className="cal-stat-label">Pace puro</span>
              <span className="cal-stat-value">{latest.pace_pure_label ?? "—"}</span>
              <span className="cal-stat-unit">descontando descansos</span>
            </div>
          </div>
        </div>
      )}

      {data.insights && data.insights.length > 0 && (
        <div className="swim-insights">
          <div className="label" style={{ marginBottom: 4 }}>Insights</div>
          <ul>
            {data.insights.map((i, idx) => (
              <li key={idx}>{i}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
