import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Readiness, SleepNight } from "../api/client";

export function SleepCard({ sleep, readiness }: { sleep: SleepNight[]; readiness: Readiness }) {
  if (sleep.length === 0) {
    return (
      <>
        <h2>Sono e recuperação</h2>
        <div className="empty">Sem dados. Rode <code>uv run garmin-relatorio ingest-garmin --what sleep</code></div>
      </>
    );
  }
  const flagColor = { verde: "#4ade80", amarelo: "#fbbf24", vermelho: "#ef4444", sem_dados: "#8b96a8" }[readiness.flag];

  return (
    <>
      <h2>Sono e recuperação</h2>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <span style={{ width: 12, height: 12, borderRadius: "50%", background: flagColor }} />
        <span style={{ fontWeight: 600, textTransform: "capitalize" }}>{readiness.flag}</span>
      </div>
      {readiness.notes.length > 0 && (
        <ul className="notes">
          {readiness.notes.map((n) => (
            <li key={n}>⚠ {n}</li>
          ))}
        </ul>
      )}
      <ResponsiveContainer width="100%" height={140}>
        <LineChart data={sleep} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
          <XAxis dataKey="date" stroke="#8b96a8" fontSize={10} tickFormatter={(d) => d.slice(5)} />
          <YAxis stroke="#8b96a8" fontSize={10} domain={[4, 10]} unit="h" />
          <Tooltip contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }} />
          <ReferenceLine y={7} stroke="#4ade80" strokeDasharray="4 4" />
          <Line type="monotone" dataKey="total_h" stroke="#60a5fa" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </>
  );
}
