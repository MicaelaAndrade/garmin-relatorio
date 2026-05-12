import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SleepDetailDashboard } from "../api/client";

const STAGE_COLORS = {
  deep: "#7c3aed",   // roxo profundo
  REM: "#60a5fa",    // azul (REM)
  light: "#94a3b8",  // cinza claro
  awake: "#fb923c",  // laranja (interrupções)
};

const VERDICT_LABEL = {
  excelente: "Excelente",
  bom: "Bom",
  regular: "Regular",
  ruim: "Ruim",
} as const;

const VERDICT_COLOR = {
  excelente: "#4ade80",
  bom: "#60a5fa",
  regular: "#fbbf24",
  ruim: "#ef4444",
} as const;

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function hoursMin(min: number): string {
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return `${h}h${String(m).padStart(2, "0")}`;
}

export function SleepDetailCard({ data }: { data: SleepDetailDashboard }) {
  if (!data.available) {
    return (
      <>
        <h2>Sono detalhado</h2>
        <div className="empty">Sem dados de sono ingeridos pra esta janela.</div>
      </>
    );
  }

  const chartData = data.series.map((n) => ({
    day: shortDate(n.date),
    deep: n.deep_min,
    REM: n.rem_min,
    light: n.light_min,
    awake: n.awake_min,
    total: n.total_min,
    score: n.score,
  }));

  return (
    <>
      <div className="cal-head">
        <h2 style={{ display: "inline" }}>Sono detalhado</h2>
        <span className="muted" style={{ marginLeft: 8, fontSize: 11 }}>
          últimos {data.days}d · {data.series.length} noites
        </span>
        {data.verdict && (
          <span
            className="zone"
            style={{
              background: `${VERDICT_COLOR[data.verdict]}33`,
              color: VERDICT_COLOR[data.verdict],
              marginLeft: "auto",
            }}
          >
            {VERDICT_LABEL[data.verdict]}
          </span>
        )}
      </div>

      <div className="cal-stats" style={{ marginBottom: 12 }}>
        <div className="cal-stat">
          <span className="cal-stat-label">Média/noite</span>
          <span className="cal-stat-value">{data.avg_total_h}h</span>
          <span className="cal-stat-unit">~{hoursMin(data.avg_total_min || 0)}</span>
        </div>
        <div className="cal-stat" title="% do tempo dormindo em sono profundo. Ideal: 13-23%.">
          <span className="cal-stat-label">Profundo</span>
          <span className="cal-stat-value" style={{ color: STAGE_COLORS.deep }}>{data.avg_deep_pct}%</span>
          <span className="cal-stat-unit">ideal 13-23%</span>
        </div>
        <div className="cal-stat" title="% do tempo em sono REM. Ideal: 20-25%.">
          <span className="cal-stat-label">REM</span>
          <span className="cal-stat-value" style={{ color: STAGE_COLORS.REM }}>{data.avg_rem_pct}%</span>
          <span className="cal-stat-unit">ideal 20-25%</span>
        </div>
        <div className="cal-stat" title="Tempo dormindo / tempo na cama. Ideal: ≥85%.">
          <span className="cal-stat-label">Eficiência</span>
          <span className="cal-stat-value" style={{ color: "var(--accent)" }}>{data.avg_efficiency_pct}%</span>
          <span className="cal-stat-unit">ideal ≥85%</span>
        </div>
        {data.avg_score != null && (
          <div className="cal-stat">
            <span className="cal-stat-label">Score Garmin</span>
            <span className="cal-stat-value">{data.avg_score}</span>
            <span className="cal-stat-unit">/ 100</span>
          </div>
        )}
      </div>

      {data.message && <p className="recommendation" style={{ marginBottom: 12, fontSize: 12 }}>{data.message}</p>}

      <div className="label" style={{ marginBottom: 4 }}>Composição diária (min)</div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
          <XAxis dataKey="day" stroke="#8b96a8" fontSize={10} />
          <YAxis stroke="#8b96a8" fontSize={10} unit="min" width={42} />
          <Tooltip
            contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
            formatter={(v: number, name: string) => [`${v} min`, name]}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="deep" stackId="a" fill={STAGE_COLORS.deep} name="Profundo" />
          <Bar dataKey="REM" stackId="a" fill={STAGE_COLORS.REM} name="REM" />
          <Bar dataKey="light" stackId="a" fill={STAGE_COLORS.light} name="Leve" />
          <Bar dataKey="awake" stackId="a" fill={STAGE_COLORS.awake} name="Acordada" />
        </BarChart>
      </ResponsiveContainer>

      {(data.nights_short || data.nights_low_score) ? (
        <div className="cal-note" style={{ marginTop: 12 }}>
          ⚠ {data.nights_short ? `${data.nights_short} noite(s) < 6h` : ""}
          {data.nights_short && data.nights_low_score ? " · " : ""}
          {data.nights_low_score ? `${data.nights_low_score} noite(s) com score < 50` : ""}
          {" "}nesta janela — pode estar influenciando seu overtraining score.
        </div>
      ) : null}

      {data.sleep_debt?.available && (
        <div
          className="cal-note"
          style={{
            marginTop: 12,
            borderLeftColor:
              data.sleep_debt.status === "alta"
                ? "var(--danger)"
                : data.sleep_debt.status === "moderada"
                ? "var(--warn)"
                : data.sleep_debt.status === "leve"
                ? "var(--info)"
                : "var(--accent)",
            background:
              data.sleep_debt.status === "alta"
                ? "rgba(239, 68, 68, 0.08)"
                : data.sleep_debt.status === "moderada"
                ? "rgba(251, 191, 36, 0.08)"
                : "rgba(96, 165, 250, 0.08)",
          }}
        >
          🛌 <strong>Sleep debt ({data.sleep_debt.days}d):</strong>{" "}
          <strong style={{ fontFamily: "ui-monospace, monospace" }}>
            {data.sleep_debt.debt_h > 0 ? "−" : "+"}{Math.abs(data.sleep_debt.debt_h)}h
          </strong>{" "}
          vs alvo {data.sleep_debt.target_h}h/noite
          {data.sleep_debt.avg_short_min_per_night
            ? ` · ~${data.sleep_debt.avg_short_min_per_night}min/noite a menos`
            : ""}
          . {data.sleep_debt.message}
        </div>
      )}
    </>
  );
}
