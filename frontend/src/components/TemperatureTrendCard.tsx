import { CartesianGrid, ResponsiveContainer, ScatterChart, Scatter, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import type { TemperatureTrend } from "../api/client";

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export function TemperatureTrendCard({ data }: { data: TemperatureTrend }) {
  if (!data.available || !data.series) {
    return (
      <>
        <h2>Temperatura nos treinos</h2>
        <div className="empty">{data.reason || "Sem dados."}</div>
      </>
    );
  }
  const scatterData = data.series
    .filter((p) => p.avg_hr != null)
    .map((p) => ({ temp: p.avg_temp_c, hr: p.avg_hr, date: shortDate(p.date) }));
  return (
    <>
      <h2>Temperatura nos treinos</h2>
      <div className="muted" style={{ fontSize: 11, marginBottom: 12 }}>
        Últimos {data.days} dias · {data.total_sessions} sessões
      </div>

      <div className="cal-stats" style={{ marginBottom: 14 }}>
        <div className="cal-stat" title="Média da (min+max)/2 nas atividades">
          <span className="cal-stat-label">Temp. média</span>
          <span className="cal-stat-value">{data.avg_temp_c}°C</span>
          <span className="cal-stat-unit">média {data.total_sessions} sessões</span>
        </div>
        <div className="cal-stat">
          <span className="cal-stat-label">Pico</span>
          <span className="cal-stat-value" style={{ color: "var(--danger)" }}>{data.max_temp_c}°C</span>
          <span className="cal-stat-unit">treino mais quente</span>
        </div>
        <div className="cal-stat" title="Treinos com max temp ≥ 30°C — heat strain significativo">
          <span className="cal-stat-label">Dias ≥ 30°C</span>
          <span className="cal-stat-value" style={{ color: "var(--warn)" }}>{data.hot_days_30plus}</span>
          <span className="cal-stat-unit">treinos quentes</span>
        </div>
        <div className="cal-stat">
          <span className="cal-stat-label">Dias &lt; 20°C</span>
          <span className="cal-stat-value" style={{ color: "var(--info)" }}>{data.cool_days_under20}</span>
          <span className="cal-stat-unit">treinos frescos</span>
        </div>
      </div>

      {scatterData.length > 0 && (
        <>
          <div className="label" style={{ marginBottom: 4 }}>Temperatura × FC média</div>
          <ResponsiveContainer width="100%" height={200}>
            <ScatterChart margin={{ top: 4, right: 8, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
              <XAxis
                type="number"
                dataKey="temp"
                name="Temp"
                unit="°C"
                stroke="#8b96a8"
                fontSize={10}
                domain={["dataMin - 2", "dataMax + 2"]}
              />
              <YAxis
                type="number"
                dataKey="hr"
                name="FC"
                unit=" bpm"
                stroke="#8b96a8"
                fontSize={10}
                domain={["dataMin - 5", "dataMax + 5"]}
              />
              <ZAxis range={[40, 40]} />
              <Tooltip
                contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
                cursor={{ strokeDasharray: "3 3" }}
                formatter={(v: number, name: string) => [v, name]}
              />
              <Scatter data={scatterData} fill="#fbbf24" />
            </ScatterChart>
          </ResponsiveContainer>
          <div className="muted" style={{ fontSize: 10, marginTop: 4 }}>
            Cada ponto = 1 treino. Tendência: mais quente → FC mais alta no mesmo esforço (heat strain ~+1bpm/°C acima de 25°C).
          </div>
        </>
      )}

      {data.insight && (
        <div className="cal-note" style={{ marginTop: 12 }}>
          💡 {data.insight}
        </div>
      )}
    </>
  );
}
