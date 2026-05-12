import { useState, type ReactElement } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BodyComposition, BodyMetric, BodyMetricRating } from "../api/client";

const RATING_COLOR: Record<string, string> = {
  good: "var(--good, #4ade80)",
  warn: "var(--warn, #fbbf24)",
  bad: "var(--danger, #ef4444)",
};

function fmtShort(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function fmtValue(m: BodyMetric): string {
  if (m.value == null) return "—";
  if (m.key === "weight_kg") return `${m.value.toFixed(1)}`;
  if (m.key === "bmi") return `${m.value.toFixed(1)}`;
  if (m.key === "bmr_kcal") return `${Math.round(m.value)}`;
  if (m.key === "visceral_fat") return `${m.value.toFixed(0)}`;
  return `${m.value.toFixed(1)}`;
}

function fmtDelta(m: BodyMetric): { text: string; color: string } | null {
  if (m.delta_4w == null) return null;
  const v = m.delta_4w;
  let color = "var(--muted)";
  // Pra peso/gordura/visceral: descer = bom (verde). Pra musculo/agua: subir = bom.
  const positiveDown = ["weight_kg", "fat_pct", "visceral_fat"];
  const positiveUp = ["muscle_pct", "water_pct"];
  if (positiveDown.includes(m.key) && v < 0) color = "var(--good, #4ade80)";
  if (positiveDown.includes(m.key) && v > 0) color = "var(--warn, #fbbf24)";
  if (positiveUp.includes(m.key) && v > 0) color = "var(--good, #4ade80)";
  if (positiveUp.includes(m.key) && v < 0) color = "var(--warn, #fbbf24)";
  const fmt =
    m.key === "bmr_kcal"
      ? `${v > 0 ? "+" : ""}${Math.round(v)}`
      : `${v > 0 ? "+" : ""}${v.toFixed(2)}`;
  return { text: `${fmt}${m.unit ? " " + m.unit : ""}`, color };
}

function badge(rating: BodyMetricRating | null): ReactElement | null {
  if (!rating) return null;
  return (
    <span
      className="bodycomp-badge"
      style={{ color: RATING_COLOR[rating.rating] || "var(--muted)" }}
    >
      {rating.label}
    </span>
  );
}

type ChartKey = "weight_kg" | "fat_pct" | "muscle_pct" | "water_pct";
const CHART_OPTIONS: { key: ChartKey; label: string; color: string; unit: string }[] = [
  { key: "weight_kg", label: "Peso", color: "#60a5fa", unit: "kg" },
  { key: "fat_pct", label: "Gordura", color: "#fbbf24", unit: "%" },
  { key: "muscle_pct", label: "Músculo", color: "#4ade80", unit: "%" },
  { key: "water_pct", label: "Água", color: "#a78bfa", unit: "%" },
];

export function BodyCompositionCard({ data }: { data: BodyComposition }) {
  const [chartKey, setChartKey] = useState<ChartKey>("weight_kg");

  if (!data.available || !data.metrics || !data.series) {
    return (
      <>
        <h2>Composição corporal</h2>
        <div className="empty">
          {data.reason || "Sem medidas de bioimpedância importadas."}
          <div className="label" style={{ marginTop: 8 }}>
            Importe com: <code>uv run garmin-relatorio ingest-zepp /path/to/export</code>
          </div>
        </div>
      </>
    );
  }

  const chartConfig = CHART_OPTIONS.find((o) => o.key === chartKey)!;
  const chartData = data.series
    .filter((s) => s[chartKey] != null)
    .map((s) => ({ date: fmtShort(s.date), value: s[chartKey] as number }));
  const totalDelta =
    chartKey === "weight_kg" || chartKey === "fat_pct" || chartKey === "muscle_pct"
      ? data.total_delta?.[chartKey]
      : undefined;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h2 style={{ margin: 0 }}>Composição corporal</h2>
        <span className="muted" style={{ fontSize: 11 }}>
          {data.count} medidas · {data.first_date && fmtShort(data.first_date)} → {data.latest_date && fmtShort(data.latest_date)} · via Zepp
        </span>
      </div>

      <div className="bodycomp-grid" style={{ marginTop: 12 }}>
        {data.metrics.map((m) => {
          const delta = fmtDelta(m);
          return (
            <div key={m.key} className="bodycomp-stat">
              <span className="bodycomp-label">{m.label}</span>
              <span className="bodycomp-value">
                {fmtValue(m)}
                {m.unit && <span className="bodycomp-unit"> {m.unit}</span>}
              </span>
              {badge(m.rating)}
              {delta && (
                <span className="bodycomp-delta" style={{ color: delta.color }}>
                  {delta.text} <span className="muted">4 medidas</span>
                </span>
              )}
            </div>
          );
        })}
      </div>

      <div className="bodycomp-chart-tabs" style={{ marginTop: 14 }}>
        {CHART_OPTIONS.map((o) => (
          <button
            key={o.key}
            type="button"
            className={`bodycomp-tab${o.key === chartKey ? " active" : ""}`}
            onClick={() => setChartKey(o.key)}
            style={{ borderColor: o.key === chartKey ? o.color : "transparent" }}
          >
            {o.label}
          </button>
        ))}
      </div>

      <div style={{ width: "100%", height: 200, marginTop: 6 }}>
        <ResponsiveContainer>
          <LineChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--muted)" }} />
            <YAxis
              tick={{ fontSize: 10, fill: "var(--muted)" }}
              domain={["dataMin - 0.5", "dataMax + 0.5"]}
              tickFormatter={(v) => `${v}${chartConfig.unit}`}
              width={40}
            />
            <Tooltip
              contentStyle={{
                background: "var(--card-bg, #1a1f2b)",
                border: "1px solid var(--border, #2a3242)",
                fontSize: 12,
              }}
              formatter={(v: number) => [`${v.toFixed(1)} ${chartConfig.unit}`, chartConfig.label]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={chartConfig.color}
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {totalDelta != null && (
        <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
          Total acumulado: {totalDelta > 0 ? "+" : ""}{totalDelta.toFixed(2)} {chartConfig.unit} desde {data.first_date && fmtShort(data.first_date)}
        </div>
      )}

      {data.insights && data.insights.length > 0 && (
        <div className="bodycomp-insights">
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
