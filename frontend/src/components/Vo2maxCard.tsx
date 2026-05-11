import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Vo2maxLatest, Vo2maxPoint } from "../api/client";

export function Vo2maxCard({ latest, series }: { latest: Vo2maxLatest; series: Vo2maxPoint[] }) {
  const runVo2 = latest.by_sport.run;

  if (!runVo2 && series.length === 0) {
    return (
      <>
        <h2>VO2max</h2>
        <div className="empty">Sem dados de VO2max no histórico.</div>
      </>
    );
  }

  return (
    <>
      <h2>VO2max (corrida)</h2>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 4 }}>
        <span className="big">{runVo2 ? runVo2.value.toFixed(0) : "—"}</span>
        <span className="label">ml/kg/min</span>
      </div>
      <div className="label">{runVo2 ? `Última medição: ${runVo2.date}` : ""}</div>

      {series.length > 0 && (
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={series} margin={{ top: 12, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
            <XAxis dataKey="date" stroke="#8b96a8" fontSize={10} tickFormatter={(d) => d.slice(2, 7)} />
            <YAxis stroke="#8b96a8" fontSize={10} domain={["dataMin - 2", "dataMax + 2"]} />
            <Tooltip contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }} />
            <Line type="monotone" dataKey="value" stroke="#4ade80" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </>
  );
}
