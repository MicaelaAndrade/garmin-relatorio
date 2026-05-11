import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { WeeklyVolume } from "../api/client";

const COLORS: Record<string, string> = {
  run: "#4ade80",
  bike: "#60a5fa",
  swim: "#fbbf24",
  strength: "#a78bfa",
  yoga: "#f472b6",
  walking: "#94a3b8",
  other: "#8b96a8",
};

const LABELS: Record<string, string> = {
  run: "Corrida",
  bike: "Bike",
  swim: "Nado",
  strength: "Força",
  yoga: "Yoga",
  walking: "Caminhada",
  other: "Outro",
};

// Ordem fixa pra legenda/empilhamento (cardio embaixo, força/yoga em cima)
const ORDER = ["run", "bike", "swim", "strength", "yoga", "walking", "other"];

export function VolumeChart({ data }: { data: WeeklyVolume[] }) {
  const byWeek: Record<string, Record<string, number> & { week: string }> = {};
  for (const w of data) {
    if (!byWeek[w.week_start]) byWeek[w.week_start] = { week: w.week_start } as never;
    // Soma de minutos por sport+semana (PT label como chave pra Legend/Tooltip ja mostrarem traduzido)
    const key = LABELS[w.sport] || w.sport;
    byWeek[w.week_start][key] = (byWeek[w.week_start][key] || 0) + w.duration_min;
  }
  const rows = Object.values(byWeek).sort((a, b) => a.week.localeCompare(b.week));
  const sportsPresent: string[] = Array.from(new Set(data.map((w) => w.sport as string)));
  const sports = ORDER.filter((s) => sportsPresent.includes(s)).concat(
    sportsPresent.filter((s) => !ORDER.includes(s)),
  );

  if (rows.length === 0) {
    return <div className="empty">Sem dados de treino. Rode <code>uv run garmin-relatorio ingest-garmin</code></div>;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
        <XAxis dataKey="week" stroke="#8b96a8" fontSize={11} tickFormatter={(d) => d.slice(5)} />
        <YAxis
          stroke="#8b96a8"
          fontSize={11}
          label={{ value: "min", angle: -90, position: "insideLeft", fill: "#8b96a8", fontSize: 11 }}
        />
        <Tooltip
          contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
          formatter={(value: number, name: string) => [`${Math.round(value)} min`, name]}
          labelFormatter={(week: string) => `Semana de ${week}`}
        />
        <Legend />
        {sports.map((sport) => (
          <Bar
            key={sport}
            dataKey={LABELS[sport] || sport}
            stackId="a"
            fill={COLORS[sport] || COLORS.other}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
