import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { WellnessDashboard, WellnessLatestStatus } from "../api/client";

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function LatestStatus({ s }: { s: WellnessLatestStatus }) {
  const hrv = s.hrv_status;
  const balanced = hrv?.status === "BALANCED";
  return (
    <div className="cal-stats" style={{ marginBottom: 14 }}>
      {hrv && (
        <div
          className="cal-stat"
          title="HRV Status do Garmin: compara seu HRV das últimas noites com sua faixa de baseline pessoal."
        >
          <span className="cal-stat-label">HRV Status</span>
          <span
            className="cal-stat-value"
            style={{ color: balanced ? "var(--good, #4ade80)" : "var(--warn, #fb923c)", fontSize: 18 }}
          >
            {hrv.status_pt}
          </span>
          <span className="cal-stat-unit">
            {hrv.last_night_avg ?? "—"}ms
            {hrv.balanced_low != null && hrv.balanced_upper != null
              ? ` · faixa ${hrv.balanced_low}–${hrv.balanced_upper}`
              : ""}
          </span>
        </div>
      )}
      {s.spo2 && (
        <div className="cal-stat" title="Saturação de oxigênio no sangue durante o sono.">
          <span className="cal-stat-label">SpO₂</span>
          <span className="cal-stat-value">{s.spo2.avg ?? "—"}%</span>
          <span className="cal-stat-unit">média · mín {s.spo2.lowest ?? "—"}%</span>
        </div>
      )}
      {s.respiration && (
        <div className="cal-stat" title="Frequência respiratória (respirações por minuto) acordada.">
          <span className="cal-stat-label">Respiração</span>
          <span className="cal-stat-value">{s.respiration.avg_waking ?? "—"}</span>
          <span className="cal-stat-unit">rpm acordada</span>
        </div>
      )}
    </div>
  );
}

export function WellnessCard({ data }: { data: WellnessDashboard }) {
  if (!data.available) {
    return (
      <>
        <h2>Recuperação & estresse</h2>
        <div className="empty">Sem dados diários ingeridos.</div>
      </>
    );
  }
  const rows = data.series.map((s) => ({
    day: shortDate(s.date),
    bb: s.body_battery,
    stress: s.stress,
    hrv: s.hrv,
    rhr: s.rhr,
  }));

  return (
    <>
      <h2>Recuperação & estresse</h2>
      <div className="muted" style={{ fontSize: 11, marginBottom: 10 }}>últimos {data.days} dias</div>

      <div className="cal-stats" style={{ marginBottom: 14 }}>
        <div className="cal-stat" title="Body Battery médio (0-100). Reservas de energia do corpo segundo o Garmin.">
          <span className="cal-stat-label">Body Battery</span>
          <span className="cal-stat-value" style={{ color: "var(--accent)" }}>{data.avg_body_battery ?? "—"}</span>
          <span className="cal-stat-unit">
            média · {data.bb_low_days || 0} dia(s) &lt; 50
          </span>
        </div>
        <div className="cal-stat" title="Stress médio (0-100). >50 já indica dia estressante.">
          <span className="cal-stat-label">Stress</span>
          <span className="cal-stat-value" style={{ color: data.avg_stress && data.avg_stress > 50 ? "var(--warn)" : "var(--info)" }}>
            {data.avg_stress ?? "—"}
          </span>
          <span className="cal-stat-unit">
            média · {data.stress_high_days || 0} dia(s) ≥ 50
          </span>
        </div>
        <div className="cal-stat" title="FC repouso média do período.">
          <span className="cal-stat-label">FC repouso</span>
          <span className="cal-stat-value">{data.avg_rhr ?? "—"}</span>
          <span className="cal-stat-unit">bpm</span>
        </div>
        <div className="cal-stat" title="HRV (variabilidade FC) noturno médio. ↑ = mais recuperado.">
          <span className="cal-stat-label">HRV</span>
          <span className="cal-stat-value">{data.avg_hrv ?? "—"}</span>
          <span className="cal-stat-unit">ms</span>
        </div>
      </div>

      {data.latest_status && <LatestStatus s={data.latest_status} />}

      <div className="label" style={{ marginBottom: 4 }}>Body Battery (0-100)</div>
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
          <XAxis dataKey="day" stroke="#8b96a8" fontSize={10} />
          <YAxis stroke="#8b96a8" fontSize={10} domain={[0, 100]} width={32} />
          <Tooltip
            contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
            formatter={(v: number) => [`${v}`, "Body Battery"]}
          />
          <Area type="monotone" dataKey="bb" stroke="#4ade80" fill="rgba(74, 222, 128, 0.18)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>

      <div className="label" style={{ marginTop: 12, marginBottom: 4 }}>Stress diário (0-100)</div>
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
          <XAxis dataKey="day" stroke="#8b96a8" fontSize={10} />
          <YAxis stroke="#8b96a8" fontSize={10} domain={[0, 100]} width={32} />
          <Tooltip
            contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
            formatter={(v: number) => [`${v}`, "Stress"]}
          />
          <Area type="monotone" dataKey="stress" stroke="#fb923c" fill="rgba(251, 146, 60, 0.18)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>

      <div className="label" style={{ marginTop: 12, marginBottom: 4 }}>HRV (variabilidade FC) · ms</div>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
          <XAxis dataKey="day" stroke="#8b96a8" fontSize={10} />
          <YAxis stroke="#8b96a8" fontSize={10} domain={["dataMin - 5", "dataMax + 5"]} width={32} />
          <Tooltip
            contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
            formatter={(v: number) => [`${v} ms`, "HRV"]}
          />
          <Line type="monotone" dataKey="hrv" stroke="#60a5fa" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </>
  );
}
