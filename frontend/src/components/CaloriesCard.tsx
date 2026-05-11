import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CaloriesDashboard } from "../api/client";

const SPORT_ICON: Record<string, string> = {
  run: "🏃",
  bike: "🚴",
  swim: "🏊",
  strength: "💪",
  yoga: "🧘",
  walking: "🚶",
  other: "•",
};

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export function CaloriesCard({ data }: { data: CaloriesDashboard }) {
  if (!data.available) {
    return (
      <>
        <h2>Calorias</h2>
        <div className="empty">
          Sem dados diários de calorias ainda. Rode{" "}
          <code>uv run garmin-relatorio ingest-export --what daily</code> ou{" "}
          <code>ingest-garmin --what daily</code>.
        </div>
      </>
    );
  }

  const current = data.current!;
  const chartData = data.daily_series.map((d) => ({
    day: shortDate(d.date),
    BMR: d.bmr || 0,
    Ativo: d.active || 0,
  }));

  return (
    <>
      <div className="cal-head">
        <h2 style={{ display: "inline" }}>Calorias</h2>
        <span className="muted" style={{ marginLeft: 8, fontSize: 11 }}>últimos {data.days} dias</span>
      </div>

      <div className="cal-stats">
        <div
          className="cal-stat"
          title="Soma de BMR (basal, 24h) + Ativo (durante exercícios) do dia"
        >
          <span className="cal-stat-label">Total hoje</span>
          <span className="cal-stat-value">{current.total ?? "—"}</span>
          <span className="cal-stat-unit">kcal · dia inteiro</span>
        </div>
        <div
          className="cal-stat"
          title={
            current.workout_per_hour
              ? `${current.workout_per_hour} kcal/h durante o(s) treino(s). Inclui o ativo + parte do BMR daquela hora.`
              : "Sem treino registrado hoje"
          }
        >
          <span className="cal-stat-label">Ativo hoje</span>
          <span className="cal-stat-value" style={{ color: "var(--accent)" }}>{current.active ?? "—"}</span>
          <span className="cal-stat-unit">
            kcal{current.workout_minutes ? ` · ${current.workout_minutes}min treino` : ""}
          </span>
          {current.workout_per_hour != null && (
            <span className="cal-rate" style={{ color: "var(--accent)" }}>
              ≈ {current.workout_per_hour} kcal/h durante treino
            </span>
          )}
        </div>
        <div
          className="cal-stat"
          title="Basal Metabolic Rate — gasto de repouso pelas 24h. Manter o corpo funcionando."
        >
          <span className="cal-stat-label">BMR (basal)</span>
          <span className="cal-stat-value" style={{ color: "var(--info)" }}>{current.bmr ?? "—"}</span>
          <span className="cal-stat-unit">kcal · 24h</span>
          {current.bmr_per_hour != null && (
            <span className="cal-rate" style={{ color: "var(--info)" }}>
              ≈ {current.bmr_per_hour} kcal/h em repouso
            </span>
          )}
        </div>
        <div className="cal-stat">
          <span className="cal-stat-label">Semana atual</span>
          <span className="cal-stat-value">{data.week_total_kcal.toLocaleString("pt-BR")}</span>
          <span className="cal-stat-unit">kcal · ativo {data.week_active_kcal}</span>
        </div>
      </div>

      {current.workout_per_hour != null && current.bmr_per_hour != null && (
        <div className="cal-note">
          💡 Durante seu treino você queima <strong>{current.workout_per_hour} kcal/h</strong>{" "}
          contra <strong>{current.bmr_per_hour} kcal/h</strong> em repouso —{" "}
          <strong>{Math.round(current.workout_per_hour / current.bmr_per_hour)}× mais</strong>.
          O BMR total parece alto porque acumula as 24h do dia.
        </div>
      )}

      <div style={{ marginTop: 12 }}>
        <div className="label" style={{ marginBottom: 4 }}>Diário (BMR + Ativo)</div>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
            <XAxis dataKey="day" stroke="#8b96a8" fontSize={10} />
            <YAxis stroke="#8b96a8" fontSize={10} unit="" width={42} />
            <Tooltip
              contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
              formatter={(v: number, name: string) => [`${v} kcal`, name]}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="BMR" stackId="a" fill="#60a5fa" />
            <Bar dataKey="Ativo" stackId="a" fill="#4ade80" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {data.by_sport.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="label" style={{ marginBottom: 6 }}>Gasto por modalidade ({data.days}d)</div>
          <div className="cal-by-sport">
            {data.by_sport.map((s) => (
              <div key={s.sport} className="cal-sport-row">
                <span style={{ fontSize: 16 }}>{SPORT_ICON[s.sport] || "•"}</span>
                <span className="cal-sport-name">{s.label}</span>
                <span className="cal-sport-sessions">{s.sessions}× </span>
                <span className="cal-sport-total">{s.total_kcal.toLocaleString("pt-BR")} kcal</span>
                <span className="cal-sport-rate">{s.avg_per_hour} kcal/h</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.references.available && (
        <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
          <div className="label" style={{ marginBottom: 8 }}>
            Referências (média {data.days}d)
          </div>
          <div className="cal-refs">
            <div className="cal-ref">
              <span className="cal-ref-label">TDEE médio</span>
              <span className="cal-ref-value">{data.average.total?.toLocaleString("pt-BR")}</span>
              <span className="cal-ref-unit">kcal/dia (gasto)</span>
            </div>
            <div className="cal-ref">
              <span className="cal-ref-label">BMR Garmin</span>
              <span className="cal-ref-value">{data.references.bmr_garmin?.toLocaleString("pt-BR")}</span>
              <span className="cal-ref-unit">kcal · usado pelo seu relógio</span>
            </div>
            <div className="cal-ref">
              <span className="cal-ref-label">BMR Mifflin-StJeor</span>
              <span className="cal-ref-value">{data.references.bmr_mifflin?.toLocaleString("pt-BR")}</span>
              <span className="cal-ref-unit">
                kcal · fórmula científica
                {data.references.bmr_diff_garmin_vs_mifflin != null && (
                  <span style={{ marginLeft: 4, color: Math.abs(data.references.bmr_diff_garmin_vs_mifflin) > 200 ? "var(--warn)" : "var(--muted)" }}>
                    (Garmin {data.references.bmr_diff_garmin_vs_mifflin > 0 ? "+" : ""}{data.references.bmr_diff_garmin_vs_mifflin})
                  </span>
                )}
              </span>
            </div>
          </div>

          {data.references.macros && (
            <>
              <div className="label" style={{ marginTop: 14, marginBottom: 6 }}>
                Macros sugeridos pra manutenção ({data.references.macros.tdee_target} kcal)
              </div>
              <div className="macros-bar">
                <span className="macros-seg macros-protein" style={{ flex: data.references.macros.protein_pct }} title={`Proteína: ${data.references.macros.protein_g}g (${data.references.macros.protein_pct}%)`} />
                <span className="macros-seg macros-carb" style={{ flex: data.references.macros.carb_pct }} title={`Carbo: ${data.references.macros.carb_g}g (${data.references.macros.carb_pct}%)`} />
                <span className="macros-seg macros-fat" style={{ flex: data.references.macros.fat_pct }} title={`Gordura: ${data.references.macros.fat_g}g (${data.references.macros.fat_pct}%)`} />
              </div>
              <div className="macros-legend">
                <div>
                  <span className="macros-dot macros-protein" /> Proteína
                  <strong> {data.references.macros.protein_g}g</strong>
                  <span className="muted"> · {data.references.macros.protein_pct}% · {data.references.macros.protein_kcal} kcal</span>
                </div>
                <div>
                  <span className="macros-dot macros-carb" /> Carbo
                  <strong> {data.references.macros.carb_g}g</strong>
                  <span className="muted"> · {data.references.macros.carb_pct}% · {data.references.macros.carb_kcal} kcal</span>
                </div>
                <div>
                  <span className="macros-dot macros-fat" /> Gordura
                  <strong> {data.references.macros.fat_g}g</strong>
                  <span className="muted"> · {data.references.macros.fat_pct}% · {data.references.macros.fat_kcal} kcal</span>
                </div>
              </div>
              <p className="cal-macros-note">
                Proteína calculada como 1.8 g/kg do seu peso (faixa atleta 1.6-2.2 g/kg). Gordura ~25% das kcal. Carbo preenche o restante.
                Esses são valores pra <strong>manter o peso</strong> — pra perder, déficit de 300-500 kcal; pra ganhar, superávit similar.
              </p>
            </>
          )}
        </div>
      )}
    </>
  );
}
