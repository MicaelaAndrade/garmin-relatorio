import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CyclePerformanceDashboard } from "../api/client";
import { formatPace } from "../api/client";

const STORAGE_KEY = "cycle_card_visible"; // mesma flag do CycleCard

export function CyclePerformanceCard({ data }: { data: CyclePerformanceDashboard }) {
  // Respeita opt-in: só mostra se o usuário aceitou ver o card de ciclo
  let visible = false;
  try {
    visible = localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    /* noop */
  }
  if (!visible) return null;

  if (!data.available) {
    return (
      <>
        <h2>Ciclo × performance</h2>
        <div className="empty">{data.reason || "Sem dados suficientes."}</div>
      </>
    );
  }
  const byPhase = data.by_phase || [];
  const paceData = byPhase
    .filter((p) => p.avg_pace_s_km != null)
    .map((p) => ({ phase: p.label, pace: p.avg_pace_s_km! / 60, color: p.color }));
  const sessionsData = byPhase.map((p) => ({ phase: p.label, sessions: p.sessions, color: p.color }));

  return (
    <>
      <h2>Ciclo × performance</h2>
      <div className="muted" style={{ fontSize: 11, marginBottom: 12 }}>
        Como suas métricas variam por fase do ciclo · {data.total_sessions_classified} sessões nos últimos {data.days}d
      </div>

      <div className="cal-stats" style={{ marginBottom: 14 }}>
        {byPhase.map((p) => (
          <div key={p.phase} className="cal-stat" style={{ borderColor: p.color }}>
            <span className="cal-stat-label" style={{ color: p.color }}>{p.label}</span>
            <span className="cal-stat-value">{p.sessions}</span>
            <span className="cal-stat-unit">
              sessões
              {p.avg_pace_s_km && ` · pace ${formatPace(p.avg_pace_s_km)}`}
              {p.avg_hr && ` · FC ${p.avg_hr}`}
            </span>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <div className="label" style={{ marginBottom: 4 }}>Sessões por fase</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={sessionsData}>
              <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
              <XAxis dataKey="phase" stroke="#8b96a8" fontSize={10} />
              <YAxis stroke="#8b96a8" fontSize={10} />
              <Tooltip contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }} />
              <Bar dataKey="sessions">
                {sessionsData.map((d, i) => (
                  <Cell key={i} fill={d.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        {paceData.length > 1 && (
          <div>
            <div className="label" style={{ marginBottom: 4 }}>Pace médio (min/km · ↓ melhor)</div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={paceData}>
                <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
                <XAxis dataKey="phase" stroke="#8b96a8" fontSize={10} />
                <YAxis
                  stroke="#8b96a8"
                  fontSize={10}
                  domain={["dataMin - 0.5", "dataMax + 0.5"]}
                  reversed
                  tickFormatter={(v: number) => `${Math.floor(v)}:${String(Math.round((v % 1) * 60)).padStart(2, "0")}`}
                />
                <Tooltip
                  contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
                  formatter={(v: number) => [`${Math.floor(v)}:${String(Math.round((v % 1) * 60)).padStart(2, "0")}/km`, "Pace"]}
                />
                <Bar dataKey="pace">
                  {paceData.map((d, i) => (
                    <Cell key={i} fill={d.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {data.insights && data.insights.length > 0 && (
        <div className="cal-note" style={{ marginTop: 12 }}>
          {data.insights.map((i, idx) => (
            <div key={idx}>💡 {i}</div>
          ))}
        </div>
      )}

      <div className="muted" style={{ fontSize: 10, marginTop: 8 }}>
        ⚠ Pace é agregado de corrida + nado (FCs comparáveis). Pra análise mais limpa, separar por sport
        (TODO). Dados sugerem padrões — não substitui orientação médica.
      </div>
    </>
  );
}
