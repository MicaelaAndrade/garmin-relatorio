import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AcwrPoint, InjuryRisk } from "../api/client";

export function InjuryRiskCard({ current, series }: { current: InjuryRisk; series: AcwrPoint[] }) {
  return (
    <>
      <h2>Risco de lesão (ACWR)</h2>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 8 }}>
        <span className="big">{current.acwr ?? "—"}</span>
        <span className={`zone ${current.zone}`}>{current.zone}</span>
      </div>
      <div className="label">Carga aguda 7d / crônica 28d</div>
      <p className="recommendation">{current.recommendation}</p>

      {series.length > 0 && (
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="acwrGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fbbf24" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#fbbf24" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
            <XAxis dataKey="day" stroke="#8b96a8" fontSize={10} tickFormatter={(d) => d.slice(5)} />
            <YAxis stroke="#8b96a8" fontSize={10} domain={[0, 2.5]} />
            <Tooltip contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }} />
            <ReferenceLine y={0.8} stroke="#60a5fa" strokeDasharray="4 4" />
            <ReferenceLine y={1.3} stroke="#4ade80" strokeDasharray="4 4" />
            <ReferenceLine y={1.5} stroke="#ef4444" strokeDasharray="4 4" />
            <Area type="monotone" dataKey="acwr" stroke="#fbbf24" fill="url(#acwrGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </>
  );
}
