import { CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PMCDashboard } from "../api/client";

const ZONE_COLOR: Record<string, string> = {
  super_fresh: "#a78bfa",
  fresh: "#4ade80",
  productive: "#60a5fa",
  overload: "#fbbf24",
  risk: "#ef4444",
};

function monthLabel(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

export function PerformanceMgmtCard({ data }: { data: PMCDashboard }) {
  if (!data.available || !data.current) {
    return (
      <>
        <h2>Performance Management (Fitness / Fatigue / Form)</h2>
        <div className="empty">Sem dados suficientes (precisa ~42 dias de histórico).</div>
      </>
    );
  }

  const c = data.current;
  const chartData = data.series.map((p) => ({
    day: monthLabel(p.date),
    CTL: p.ctl,
    ATL: p.atl,
    TSB: p.tsb,
  }));

  const zoneColor = ZONE_COLOR[data.zone || "productive"];

  return (
    <>
      <div className="cal-head">
        <h2 style={{ display: "inline" }}>Performance Management</h2>
        <span className="muted" style={{ marginLeft: 8, fontSize: 11 }}>
          Fitness · Fatigue · Form · últimos {data.days} dias
        </span>
        <span
          className="zone"
          style={{ background: `${zoneColor}33`, color: zoneColor, marginLeft: "auto" }}
        >
          {data.zone_label}
        </span>
      </div>

      <div className="cal-stats" style={{ marginBottom: 14 }}>
        <div className="cal-stat" title="Chronic Training Load (média ponderada 42d) — sua FITNESS acumulada">
          <span className="cal-stat-label">CTL · Fitness</span>
          <span className="cal-stat-value" style={{ color: "var(--info)" }}>{c.ctl}</span>
          <span className="cal-stat-unit">
            42d média ponderada
            {data.ctl_delta_4w != null && (
              <span style={{ marginLeft: 4, color: data.ctl_delta_4w > 0 ? "var(--accent)" : "var(--muted)" }}>
                ({data.ctl_delta_4w > 0 ? "+" : ""}{data.ctl_delta_4w} em 4 sem)
              </span>
            )}
          </span>
        </div>
        <div className="cal-stat" title="Acute Training Load (média 7d) — sua FATIGUE aguda">
          <span className="cal-stat-label">ATL · Fatigue</span>
          <span className="cal-stat-value" style={{ color: "var(--warn)" }}>{c.atl}</span>
          <span className="cal-stat-unit">7d média ponderada</span>
        </div>
        <div
          className="cal-stat"
          title="Training Stress Balance (CTL − ATL) — sua FORM/frescor. Positivo = recuperada, negativo = fadigada."
        >
          <span className="cal-stat-label">TSB · Form</span>
          <span className="cal-stat-value" style={{ color: zoneColor }}>
            {c.tsb > 0 ? "+" : ""}{c.tsb}
          </span>
          <span className="cal-stat-unit">CTL − ATL</span>
        </div>
        <div className="cal-stat" title="TRIMP do dia (carga do treino de hoje)">
          <span className="cal-stat-label">Carga hoje</span>
          <span className="cal-stat-value">{c.load}</span>
          <span className="cal-stat-unit">TRIMP</span>
        </div>
      </div>

      <p className="recommendation" style={{ fontSize: 12, marginBottom: 12 }}>{data.message}</p>

      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
          <XAxis
            dataKey="day"
            stroke="#8b96a8"
            fontSize={10}
            interval={Math.floor(chartData.length / 8)}
          />
          <YAxis stroke="#8b96a8" fontSize={10} />
          <Tooltip
            contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
            formatter={(v: number, name: string) => [v.toFixed(1), name]}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine y={0} stroke="#8b96a8" strokeDasharray="3 3" />
          <Line type="monotone" dataKey="CTL" stroke="#60a5fa" strokeWidth={2.5} dot={false} name="Fitness (CTL)" />
          <Line type="monotone" dataKey="ATL" stroke="#fbbf24" strokeWidth={2} dot={false} name="Fatigue (ATL)" />
          <Line type="monotone" dataKey="TSB" stroke="#4ade80" strokeWidth={2} dot={false} name="Form (TSB)" strokeDasharray="5 3" />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="cal-note" style={{ marginTop: 12 }}>
        <strong>Como ler:</strong> CTL (azul) sobe = mais condicionada · ATL (amarelo) acima de CTL =
        fadigada · TSB (verde) positivo = pronta pra esforço grande (ideal pra prova). TSB &lt; −30 = alto risco.
      </div>
    </>
  );
}
