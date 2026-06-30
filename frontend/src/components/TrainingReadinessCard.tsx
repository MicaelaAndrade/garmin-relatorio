import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TrainingReadinessDashboard } from "../api/client";

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function scoreColor(score: number | null | undefined): string {
  if (score == null) return "var(--muted)";
  if (score >= 75) return "var(--good, #4ade80)";
  if (score >= 50) return "var(--warn, #fb923c)";
  return "var(--danger, #ef4444)";
}

export function TrainingReadinessCard({ data }: { data: TrainingReadinessDashboard }) {
  if (!data.available || (!data.latest && !data.status)) {
    return (
      <>
        <h2>Prontidão para treino</h2>
        <div className="empty">Sem dados do Garmin (Training Readiness exige FR265).</div>
      </>
    );
  }

  const latest = data.latest;
  const status = data.status;
  const rows = data.series.map((s) => ({ day: shortDate(s.date), score: s.score }));

  return (
    <>
      <h2>Prontidão para treino</h2>
      <div className="muted" style={{ fontSize: 11, marginBottom: 10 }}>
        Training Readiness do Garmin (FR265) · últimos {data.days} dias
      </div>

      <div className="cal-stats" style={{ marginBottom: 14 }}>
        {latest && (
          <div
            className="cal-stat"
            title="Training Readiness (0-100): combina sono, recuperação, HRV, carga aguda e stress para dizer se o corpo está pronto para treinar forte."
          >
            <span className="cal-stat-label">Prontidão hoje</span>
            <span className="cal-stat-value" style={{ color: scoreColor(latest.score), fontSize: 24 }}>
              {latest.score ?? "—"}
            </span>
            <span className="cal-stat-unit">{latest.level_pt ?? "—"}</span>
          </div>
        )}
        {status && (
          <div
            className="cal-stat"
            title="Training Status do Garmin: leitura de tendência de fitness (produtivo, mantendo, recuperação, overreaching...)."
          >
            <span className="cal-stat-label">Status</span>
            <span className="cal-stat-value" style={{ fontSize: 18 }}>{status.status_pt ?? "—"}</span>
            <span className="cal-stat-unit">tendência de fitness</span>
          </div>
        )}
        {status && status.acwr_percent != null && (
          <div
            className="cal-stat"
            title="ACWR oficial do Garmin (carga aguda : crônica). Compare com o card de risco de lesão (ACWR caseiro)."
          >
            <span className="cal-stat-label">ACWR Garmin</span>
            <span
              className="cal-stat-value"
              style={{ color: status.acwr_status === "OPTIMAL" ? "var(--good, #4ade80)" : "var(--warn, #fb923c)" }}
            >
              {status.acwr_percent}%
            </span>
            <span className="cal-stat-unit">{status.acwr_status_pt ?? ""}</span>
          </div>
        )}
        {latest && latest.recovery_time_h != null && (
          <div className="cal-stat" title="Tempo de recuperação restante recomendado pelo Garmin.">
            <span className="cal-stat-label">Recuperação</span>
            <span className="cal-stat-value">{latest.recovery_time_h}</span>
            <span className="cal-stat-unit">h restantes</span>
          </div>
        )}
      </div>

      {latest?.feedback && (
        <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
          💬 {latest.feedback}
        </div>
      )}

      {rows.length > 1 && (
        <>
          <div className="label" style={{ marginBottom: 4 }}>Prontidão (0-100)</div>
          <ResponsiveContainer width="100%" height={130}>
            <AreaChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
              <XAxis dataKey="day" stroke="#8b96a8" fontSize={10} />
              <YAxis stroke="#8b96a8" fontSize={10} domain={[0, 100]} width={32} />
              <Tooltip
                contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
                formatter={(v: number) => [`${v}`, "Prontidão"]}
              />
              <Area type="monotone" dataKey="score" stroke="#a78bfa" fill="rgba(167, 139, 250, 0.18)" strokeWidth={2} connectNulls />
            </AreaChart>
          </ResponsiveContainer>
        </>
      )}
    </>
  );
}
