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
import type { RunTechniqueProgress, RunTechniqueTrend } from "../api/client";

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function trendArrow(t: RunTechniqueTrend | undefined): string {
  if (!t || !t.improvement) return "";
  if (t.improvement === "up") return "↑";
  if (t.improvement === "down") return "↓";
  return "→";
}

function trendColor(t: RunTechniqueTrend | undefined): string {
  if (!t || !t.improvement) return "var(--muted)";
  if (t.improvement === "up") return "var(--good, #4ade80)";
  if (t.improvement === "down") return "var(--danger, #ef4444)";
  return "var(--muted)";
}

type MetricKey = "vertical_ratio" | "cadence" | "gct" | "stride_length" | "norm_power";
const METRICS: {
  key: MetricKey;
  label: string;
  unit: string;
  color: string;
  targetKey?: "vertical_ratio" | "cadence" | "gct";
}[] = [
  { key: "vertical_ratio", label: "Vertical ratio", unit: "%", color: "#4ade80", targetKey: "vertical_ratio" },
  { key: "cadence", label: "Cadência", unit: "spm", color: "#60a5fa", targetKey: "cadence" },
  { key: "gct", label: "Contato c/ solo", unit: "ms", color: "#fbbf24", targetKey: "gct" },
  { key: "stride_length", label: "Passada", unit: "cm", color: "#a78bfa" },
  { key: "norm_power", label: "Potência", unit: "W", color: "#f472b6" },
];

function fmtVal(key: MetricKey, v: number | null | undefined): string {
  if (v == null) return "—";
  if (key === "vertical_ratio") return `${v.toFixed(1)}%`;
  if (key === "stride_length") return `${v.toFixed(0)}cm`;
  if (key === "norm_power") return `${v.toFixed(0)}W`;
  return v.toFixed(0);
}

export function RunTechniqueCard({ data }: { data: RunTechniqueProgress }) {
  const [activeMetric, setActiveMetric] = useState<MetricKey>("vertical_ratio");

  if (!data.available || !data.sessions || data.sessions.length === 0) {
    return (
      <>
        <h2>Evolução técnica · Corrida</h2>
        <div className="empty">Sem corridas registradas ainda.</div>
      </>
    );
  }

  const chartData = data.sessions.map((s) => ({
    date: shortDate(s.date),
    vertical_ratio: s.vertical_ratio,
    cadence: s.cadence,
    gct: s.gct,
    stride_length: s.stride_length,
    norm_power: s.norm_power,
  }));

  const visibleMetrics = METRICS.filter((m) => m.key !== "norm_power" || data.power_available);
  const metric = METRICS.find((m) => m.key === activeMetric)!;
  const target = metric.targetKey ? data.targets[metric.targetKey] : null;
  const latest = data.latest;

  const valuesForY = chartData.map((d) => d[metric.key]).filter((v): v is number => v != null);
  const baseVals = target != null ? [...valuesForY, target] : valuesForY;
  const yMin = baseVals.length ? Math.min(...baseVals) : 0;
  const yMax = baseVals.length ? Math.max(...baseVals) : 1;
  const pad = (yMax - yMin) * 0.1 || 0.5;

  return (
    <>
      <h2>Evolução técnica · Corrida</h2>
      <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>
        Últimas {data.count} corridas · running dynamics do acelerômetro
        {target != null ? " · linha tracejada = alvo" : ""}
      </div>
      {data.power_available && (
        <div className="muted" style={{ fontSize: 10, marginBottom: 10, opacity: 0.8 }}>
          ⚡ Potência de corrida disponível (FR265, barômetro íntegro desde 18/06). Corridas anteriores ao FR265 ficam sem potência — o dado do glitch foi descartado.
        </div>
      )}

      <div className="swim-metric-tabs" style={{ marginBottom: 10 }}>
        {visibleMetrics.map((m) => {
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
                {fmtVal(m.key, tr?.current)}
              </span>
              <span className="swim-metric-tab-delta" style={{ color: trendColor(tr) }}>
                {trendArrow(tr)}{" "}
                {tr?.delta != null
                  ? `${tr.delta > 0 ? "+" : ""}${tr.delta.toFixed(m.key === "vertical_ratio" ? 1 : 0)}`
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
              tickFormatter={(v) => (metric.key === "vertical_ratio" ? `${v}%` : String(v))}
            />
            <Tooltip
              contentStyle={{
                background: "var(--card-bg, #1a1f2b)",
                border: "1px solid var(--border, #2a3242)",
                fontSize: 12,
              }}
              formatter={(v: number) => fmtVal(metric.key, v)}
            />
            {target != null && (
              <ReferenceLine
                y={target}
                stroke={metric.color}
                strokeDasharray="4 4"
                strokeOpacity={0.5}
                label={{
                  value: `alvo ${metric.key === "vertical_ratio" ? `${target}%` : target}`,
                  fill: "var(--muted)",
                  fontSize: 10,
                  position: "insideTopRight",
                }}
              />
            )}
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
            Última corrida · {shortDate(latest.date)} · {latest.distance_km}km em {latest.duration_min}min
          </div>
          <div className="swim-latest-grid">
            <div className="swim-latest-stat">
              <span className="cal-stat-label">Vertical ratio</span>
              <span className="cal-stat-value">{latest.vertical_ratio?.toFixed(1) ?? "—"}</span>
              <span className="cal-stat-unit">% · alvo &lt; {data.targets.vertical_ratio}</span>
            </div>
            <div className="swim-latest-stat">
              <span className="cal-stat-label">Cadência</span>
              <span className="cal-stat-value">{latest.cadence ?? "—"}</span>
              <span className="cal-stat-unit">spm · alvo ~{data.targets.cadence}</span>
            </div>
            <div className="swim-latest-stat">
              <span className="cal-stat-label">Contato c/ solo</span>
              <span className="cal-stat-value">{latest.gct ?? "—"}</span>
              <span className="cal-stat-unit">ms · alvo ~{data.targets.gct}</span>
            </div>
            <div className="swim-latest-stat">
              <span className="cal-stat-label">Passada</span>
              <span className="cal-stat-value">{latest.stride_length ?? "—"}</span>
              <span className="cal-stat-unit">cm</span>
            </div>
            {latest.norm_power != null && (
              <>
                <div className="swim-latest-stat">
                  <span className="cal-stat-label">Potência norm.</span>
                  <span className="cal-stat-value">{latest.norm_power}</span>
                  <span className="cal-stat-unit">
                    W{latest.w_per_kg != null ? ` · ${latest.w_per_kg} W/kg` : ""}
                  </span>
                </div>
                <div className="swim-latest-stat">
                  <span className="cal-stat-label">Variabilidade</span>
                  <span className="cal-stat-value">{latest.variability_index?.toFixed(3) ?? "—"}</span>
                  <span className="cal-stat-unit">norm/méd · alvo ≤ {data.targets.variability_index}</span>
                </div>
              </>
            )}
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
