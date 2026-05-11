import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CaloriesDashboard } from "../api/client";

const SPORT_ICON: Record<string, string> = {
  run: "🏃",
  bike: "🚴",
  swim: "🏊",
  strength: "💪",
  yoga: "🧘",
  walking: "🚶",
  other: "•",
};

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export function CaloriesCard({ data }: { data: CaloriesDashboard }) {
  if (!data.available) {
    return (
      <>
        <h2>Calorias</h2>
        <div className="empty">
          Sem dados diários de calorias ainda. Rode{" "}
          <code>uv run garmin-relatorio ingest-export --what daily</code> ou{" "}
          <code>ingest-garmin --what daily</code>.
        </div>
      </>
    );
  }

  const current = data.current!;
  const chartData = data.daily_series.map((d) => ({
    day: shortDate(d.date),
    BMR: d.bmr || 0,
    Ativo: d.active || 0,
  }));

  return (
    <>
      <div className="cal-head">
        <h2 style={{ display: "inline" }}>Calorias</h2>
        <span className="muted" style={{ marginLeft: 8, fontSize: 11 }}>últimos {data.days} dias</span>
      </div>

      <div className="cal-stats">
        <div className="cal-stat">
          <span className="cal-stat-label">Total hoje</span>
          <span className="cal-stat-value">{current.total ?? "—"}</span>
          <span className="cal-stat-unit">kcal</span>
        </div>
        <div className="cal-stat">
          <span className="cal-stat-label">Ativo hoje</span>
          <span className="cal-stat-value" style={{ color: "var(--accent)" }}>{current.active ?? "—"}</span>
          <span className="cal-stat-unit">kcal</span>
        </div>
        <div className="cal-stat">
          <span className="cal-stat-label">BMR (basal)</span>
          <span className="cal-stat-value" style={{ color: "var(--info)" }}>{current.bmr ?? "—"}</span>
          <span className="cal-stat-unit">kcal</span>
        </div>
        <div className="cal-stat">
          <span className="cal-stat-label">Semana atual</span>
          <span className="cal-stat-value">{data.week_total_kcal.toLocaleString("pt-BR")}</span>
          <span className="cal-stat-unit">kcal · ativo {data.week_active_kcal}</span>
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <div className="label" style={{ marginBottom: 4 }}>Diário (BMR + Ativo)</div>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
            <XAxis dataKey="day" stroke="#8b96a8" fontSize={10} />
            <YAxis stroke="#8b96a8" fontSize={10} unit="" width={42} />
            <Tooltip
              contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
              formatter={(v: number, name: string) => [`${v} kcal`, name]}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="BMR" stackId="a" fill="#60a5fa" />
            <Bar dataKey="Ativo" stackId="a" fill="#4ade80" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {data.by_sport.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="label" style={{ marginBottom: 6 }}>Gasto por modalidade ({data.days}d)</div>
          <div className="cal-by-sport">
            {data.by_sport.map((s) => (
              <div key={s.sport} className="cal-sport-row">
                <span style={{ fontSize: 16 }}>{SPORT_ICON[s.sport] || "•"}</span>
                <span className="cal-sport-name">{s.label}</span>
                <span className="cal-sport-sessions">{s.sessions}× </span>
                <span className="cal-sport-total">{s.total_kcal.toLocaleString("pt-BR")} kcal</span>
                <span className="cal-sport-rate">{s.avg_per_hour} kcal/h</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
