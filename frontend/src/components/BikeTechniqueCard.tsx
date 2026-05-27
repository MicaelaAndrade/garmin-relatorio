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
import type { BikeTechniqueProgress, BikeTechniqueTrend } from "../api/client";

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function trendArrow(t: BikeTechniqueTrend | undefined): string {
  if (!t || !t.improvement) return "";
  if (t.improvement === "up") return "↑";
  if (t.improvement === "down") return "↓";
  return "→";
}

function trendColor(t: BikeTechniqueTrend | undefined): string {
  if (!t || !t.improvement) return "var(--muted)";
  if (t.improvement === "up") return "var(--good, #4ade80)";
  if (t.improvement === "down") return "var(--danger, #ef4444)";
  return "var(--muted)";
}

type MetricKey = "efficiency" | "cardiac_drift_pct" | "rpe";
const METRICS: {
  key: MetricKey;
  label: string;
  unit: string;
  color: string;
  hasTarget: boolean;
}[] = [
  { key: "efficiency", label: "Eficiência aeróbica", unit: "km/h ÷ 100bpm", color: "#4ade80", hasTarget: true },
  { key: "cardiac_drift_pct", label: "Deriva cardíaca", unit: "%", color: "#fbbf24", hasTarget: true },
  { key: "rpe", label: "RPE percebido", unit: "1–10", color: "#60a5fa", hasTarget: false },
];

function fmtVal(key: MetricKey, v: number | null | undefined): string {
  if (v == null) return "—";
  if (key === "efficiency") return v.toFixed(1);
  if (key === "cardiac_drift_pct") return `${v.toFixed(1)}%`;
  return v.toFixed(1);
}

export function BikeTechniqueCard({ data }: { data: BikeTechniqueProgress }) {
  const [activeMetric, setActiveMetric] = useState<MetricKey>("efficiency");

  if (!data.available || !data.sessions || data.sessions.length === 0) {
    return (
      <>
        <h2>Evolução técnica · Ciclismo</h2>
        <div className="empty">Sem pedaladas registradas ainda.</div>
      </>
    );
  }

  const chartData = data.sessions.map((s) => ({
    date: shortDate(s.date),
    efficiency: s.efficiency,
    cardiac_drift_pct: s.cardiac_drift_pct,
    rpe: s.rpe,
    distance_km: s.distance_km,
  }));

  const metric = METRICS.find((m) => m.key === activeMetric)!;
  const target =
    metric.key === "efficiency"
      ? data.targets.efficiency
      : metric.key === "cardiac_drift_pct"
        ? data.targets.drift_pct
        : null;
  const latest = data.latest;

  const valuesForY = chartData
    .map((d) => d[metric.key])
    .filter((v): v is number => v != null);
  const baseVals = target != null ? [...valuesForY, target] : valuesForY;
  const yMin = baseVals.length ? Math.min(...baseVals) : 0;
  const yMax = baseVals.length ? Math.max(...baseVals) : 1;
  const pad = (yMax - yMin) * 0.1 || 0.5;

  const cov = data.coverage;
  const covNote =
    activeMetric === "cardiac_drift_pct"
      ? `${cov?.cardiac_drift_pct ?? 0} sessões com splits`
      : activeMetric === "rpe"
        ? `${cov?.rpe ?? 0} sessões com RPE`
        : `${cov?.efficiency ?? 0} sessões`;

  return (
    <>
      <h2>Evolução técnica · Ciclismo</h2>
      <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>
        Últimas {data.count} pedaladas · {covNote}
        {target != null ? " · linha tracejada = alvo" : ""}
      </div>
      {data.no_power_meter && (
        <div className="muted" style={{ fontSize: 10, marginBottom: 10, opacity: 0.75 }}>
          ⚠️ Sem medidor de potência — métricas de watts (NP, IF, TSS) não disponíveis. Análise baseada em velocidade, FC e esforço percebido.
        </div>
      )}

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
                {fmtVal(m.key, tr?.current)}
              </span>
              <span className="swim-metric-tab-delta" style={{ color: trendColor(tr) }}>
                {trendArrow(tr)}{" "}
                {tr?.delta != null
                  ? `${tr.delta > 0 ? "+" : ""}${tr.delta.toFixed(1)}${m.key === "cardiac_drift_pct" ? "pp" : ""}`
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
              tickFormatter={(v) => (metric.key === "cardiac_drift_pct" ? `${v}%` : String(v))}
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
                  value: `alvo ${metric.key === "cardiac_drift_pct" ? `${target}%` : target}`,
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
            Última pedalada · {shortDate(latest.date)} · {latest.distance_km}km em {latest.duration_min}min
          </div>
          <div className="swim-latest-grid">
            <div className="swim-latest-stat">
              <span className="cal-stat-label">Eficiência</span>
              <span className="cal-stat-value">{latest.efficiency?.toFixed(1) ?? "—"}</span>
              <span className="cal-stat-unit">km/h ÷ 100bpm</span>
            </div>
            <div className="swim-latest-stat">
              <span className="cal-stat-label">Vel · FC</span>
              <span className="cal-stat-value">
                {latest.avg_speed_kmh ?? "—"}
                <span style={{ fontSize: 12, opacity: 0.6 }}> · {latest.avg_hr ?? "—"}</span>
              </span>
              <span className="cal-stat-unit">km/h · bpm</span>
            </div>
            <div className="swim-latest-stat">
              <span className="cal-stat-label">Deriva</span>
              <span className="cal-stat-value">
                {latest.cardiac_drift_pct != null ? `${latest.cardiac_drift_pct}%` : "—"}
              </span>
              <span className="cal-stat-unit">alvo ≤ {data.targets.drift_pct}%</span>
            </div>
            <div className="swim-latest-stat">
              <span className="cal-stat-label">RPE · sensação</span>
              <span className="cal-stat-value">
                {latest.rpe ?? "—"}
                {latest.feel_label ? (
                  <span style={{ fontSize: 12, opacity: 0.6 }}> · {latest.feel_label}</span>
                ) : null}
              </span>
              <span className="cal-stat-unit">esforço percebido</span>
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
