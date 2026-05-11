import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Polarization, ZoneWeek } from "../api/client";

const ZONE_COLORS = {
  Z1: "#60a5fa",
  Z2: "#4ade80",
  Z3: "#fbbf24",
  Z4: "#fb923c",
  Z5: "#ef4444",
};

const VERDICT_LABEL = {
  polarizado: "Polarizado (80/20)",
  base: "Base aerobica",
  limiar: "Zona cinza (Z3)",
  misto: "Misto",
  sem_dados: "Sem dados",
} as const;

const VERDICT_COLOR = {
  polarizado: "#4ade80",
  base: "#60a5fa",
  limiar: "#fb923c",
  misto: "#fbbf24",
  sem_dados: "#8b96a8",
} as const;

const SPORT_TITLE: Record<string, { icon: string; label: string }> = {
  run: { icon: "🏃", label: "Corrida" },
  bike: { icon: "🚴", label: "Bike" },
  swim: { icon: "🏊", label: "Nado" },
};

export function ZonesCard({
  weekly,
  pol,
  sport,
}: {
  weekly: ZoneWeek[];
  pol: Polarization;
  sport?: "run" | "bike" | "swim";
}) {
  const title = sport ? SPORT_TITLE[sport] : null;
  const heading = title ? (
    <h2>
      <span style={{ marginRight: 6 }}>{title.icon}</span>
      {title.label} · Z1-Z5
    </h2>
  ) : (
    <h2>Distribuição Z1-Z5</h2>
  );

  if (weekly.length === 0) {
    return (
      <>
        {heading}
        <div className="empty">Sem dados de zonas pra {title?.label.toLowerCase() || "esta modalidade"}.</div>
      </>
    );
  }
  const chartData = weekly.map((w) => ({
    week: w.week_start,
    Z1: w.z1_min,
    Z2: w.z2_min,
    Z3: w.z3_min,
    Z4: w.z4_min,
    Z5: w.z5_min,
  }));
  const totalH = Math.round((pol.total_min || 0) / 60);

  return (
    <>
      {heading}
      <div style={{ marginBottom: 10 }}>
        <span
          className="zone"
          style={{ background: `${VERDICT_COLOR[pol.verdict]}33`, color: VERDICT_COLOR[pol.verdict] }}
        >
          {VERDICT_LABEL[pol.verdict]}
        </span>
        <span className="label" style={{ marginLeft: 10, fontSize: 11 }}>
          28d · {totalH}h
        </span>
      </div>
      {pol.low_pct !== null && (
        <div className="zones-pct">
          <span style={{ color: ZONE_COLORS.Z1 }}>Z1-Z2 {pol.low_pct}%</span>
          <span style={{ color: ZONE_COLORS.Z3 }}>Z3 {pol.mid_pct}%</span>
          <span style={{ color: ZONE_COLORS.Z5 }}>Z4-Z5 {pol.high_pct}%</span>
        </div>
      )}
      <p className="recommendation" style={{ marginBottom: 10, fontSize: 12 }}>{pol.message}</p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
          <XAxis dataKey="week" stroke="#8b96a8" fontSize={9} tickFormatter={(d) => d.slice(5)} />
          <YAxis stroke="#8b96a8" fontSize={9} unit="m" width={32} />
          <Tooltip contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }} />
          <Bar dataKey="Z1" stackId="a" fill={ZONE_COLORS.Z1} />
          <Bar dataKey="Z2" stackId="a" fill={ZONE_COLORS.Z2} />
          <Bar dataKey="Z3" stackId="a" fill={ZONE_COLORS.Z3} />
          <Bar dataKey="Z4" stackId="a" fill={ZONE_COLORS.Z4} />
          <Bar dataKey="Z5" stackId="a" fill={ZONE_COLORS.Z5} />
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}
