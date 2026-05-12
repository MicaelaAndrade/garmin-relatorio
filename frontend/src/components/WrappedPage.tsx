import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchWrapped, type WrappedDashboard } from "../api/client";

const SPORT_ICON: Record<string, string> = {
  run: "🏃",
  bike: "🚴",
  swim: "🏊",
  strength: "💪",
  yoga: "🧘",
  walking: "🚶",
};

function formatDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "long" });
}

export function WrappedPage({ onClose }: { onClose: () => void }) {
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState<WrappedDashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchWrapped(year)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [year]);

  return (
    <div className="wrapped-overlay">
      <div className="wrapped-page">
        <div className="wrapped-head">
          <div>
            <span className="wrapped-tag">WRAPPED</span>
            <h1 className="wrapped-year">{year}</h1>
          </div>
          <div className="wrapped-controls">
            <button className="btn" onClick={() => setYear(year - 1)}>← {year - 1}</button>
            {year < new Date().getFullYear() && (
              <button className="btn" onClick={() => setYear(year + 1)}>{year + 1} →</button>
            )}
            <button className="btn" onClick={onClose}>Fechar ✕</button>
          </div>
        </div>

        {loading && <div className="empty" style={{ marginTop: 40 }}>Carregando…</div>}
        {!loading && (!data || !data.available) && (
          <div className="empty" style={{ marginTop: 40 }}>Sem dados em {year}.</div>
        )}
        {!loading && data?.available && data.totals && (
          <>
            <div className="wrapped-hero">
              <div className="wrapped-stat-big">
                <span className="wrapped-stat-label">Sessões</span>
                <span className="wrapped-stat-num">{data.totals.sessions}</span>
              </div>
              <div className="wrapped-stat-big">
                <span className="wrapped-stat-label">Quilômetros</span>
                <span className="wrapped-stat-num">{data.totals.km.toLocaleString("pt-BR")}</span>
                <span className="wrapped-stat-unit">km percorridos</span>
              </div>
              <div className="wrapped-stat-big">
                <span className="wrapped-stat-label">Horas treinando</span>
                <span className="wrapped-stat-num">{data.totals.hours}h</span>
                <span className="wrapped-stat-unit">
                  ~{Math.round(data.totals.hours / data.totals.active_days * 60)} min/dia ativo
                </span>
              </div>
              <div className="wrapped-stat-big">
                <span className="wrapped-stat-label">Calorias queimadas</span>
                <span className="wrapped-stat-num">{data.totals.kcal_activities.toLocaleString("pt-BR")}</span>
                <span className="wrapped-stat-unit">só nos treinos</span>
              </div>
            </div>

            <div className="wrapped-grid">
              {data.top_sport && (
                <div className="wrapped-card wrapped-card-feature">
                  <span className="wrapped-card-label">Seu esporte favorito</span>
                  <div style={{ fontSize: 64, lineHeight: 1 }}>{SPORT_ICON[data.top_sport.sport]}</div>
                  <strong style={{ fontSize: 28 }}>{data.top_sport.label}</strong>
                  <span className="muted">
                    {data.top_sport.sessions} sessões · {data.top_sport.pct_of_sessions}% do total · {data.top_sport.total_km.toFixed(1)}km
                  </span>
                </div>
              )}
              {data.best_month && (
                <div className="wrapped-card wrapped-card-feature">
                  <span className="wrapped-card-label">Melhor mês</span>
                  <div style={{ fontSize: 48 }}>📈</div>
                  <strong style={{ fontSize: 24 }}>{data.best_month.label}</strong>
                  <span className="muted">
                    {data.best_month.sessions} sessões · {data.best_month.total_km.toFixed(1)}km · {data.best_month.total_hours}h
                  </span>
                </div>
              )}
              {data.fav_weekday && (
                <div className="wrapped-card wrapped-card-feature">
                  <span className="wrapped-card-label">Dia da semana favorito</span>
                  <div style={{ fontSize: 48 }}>📅</div>
                  <strong style={{ fontSize: 24 }}>{data.fav_weekday.label}</strong>
                  <span className="muted">{data.fav_weekday.sessions} sessões nesse dia da semana</span>
                </div>
              )}
              {data.longest_streak && data.longest_streak.days > 1 && (
                <div className="wrapped-card wrapped-card-feature">
                  <span className="wrapped-card-label">Maior streak</span>
                  <div style={{ fontSize: 48 }}>🔥</div>
                  <strong style={{ fontSize: 28 }}>{data.longest_streak.days} dias</strong>
                  <span className="muted">
                    {formatDate(data.longest_streak.start)} → {formatDate(data.longest_streak.end)}
                  </span>
                </div>
              )}
              {data.biggest_distance && (
                <div className="wrapped-card wrapped-card-feature">
                  <span className="wrapped-card-label">Maior distância</span>
                  <div style={{ fontSize: 48 }}>{SPORT_ICON[data.biggest_distance.sport] || "🏆"}</div>
                  <strong style={{ fontSize: 24 }}>{data.biggest_distance.distance_km.toFixed(1)}km</strong>
                  <span className="muted">{data.biggest_distance.label} em {formatDate(data.biggest_distance.date)}</span>
                </div>
              )}
              {data.longest_workout && (
                <div className="wrapped-card wrapped-card-feature">
                  <span className="wrapped-card-label">Treino mais longo</span>
                  <div style={{ fontSize: 48 }}>⏱️</div>
                  <strong style={{ fontSize: 24 }}>{data.longest_workout.duration_h.toFixed(1)}h</strong>
                  <span className="muted">{data.longest_workout.label} em {formatDate(data.longest_workout.date)}</span>
                </div>
              )}
            </div>

            <div className="wrapped-card" style={{ marginTop: 16 }}>
              <span className="wrapped-card-label">Sua jornada mês a mês</span>
              <div style={{ marginTop: 8 }}>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={data.monthly_series}>
                    <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
                    <XAxis dataKey="label" stroke="#8b96a8" fontSize={11} />
                    <YAxis stroke="#8b96a8" fontSize={11} />
                    <Tooltip
                      contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
                      formatter={(v: number, name: string) =>
                        name === "sessions" ? [`${v} sessões`, "Sessões"] : [`${v}km`, "Distância"]
                      }
                    />
                    <Bar dataKey="sessions" fill="#4ade80" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="wrapped-card" style={{ marginTop: 16 }}>
              <span className="wrapped-card-label">Esporte por esporte</span>
              <div className="wrapped-sports-list">
                {data.sport_stats?.map((s) => (
                  <div key={s.sport} className="wrapped-sport-row">
                    <span style={{ fontSize: 22 }}>{SPORT_ICON[s.sport] || "•"}</span>
                    <span className="wrapped-sport-name">{s.label}</span>
                    <span className="wrapped-sport-stat">
                      <strong>{s.sessions}</strong> sessões
                    </span>
                    <span className="wrapped-sport-stat">
                      <strong>{s.total_km.toFixed(1)}</strong> km
                    </span>
                    <span className="wrapped-sport-stat">
                      <strong>{s.total_hours.toFixed(1)}</strong> h
                    </span>
                    <span className="wrapped-sport-stat">
                      <strong>{s.total_kcal.toLocaleString("pt-BR")}</strong> kcal
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="wrapped-grid" style={{ marginTop: 16 }}>
              <div className="wrapped-card">
                <span className="wrapped-card-label">Elevação acumulada</span>
                <strong style={{ fontSize: 36 }}>{(data.totals.elevation_m / 1000).toFixed(1)}km</strong>
                <span className="muted">de subida vertical no ano · {data.totals.elevation_m.toLocaleString("pt-BR")}m</span>
              </div>
              <div className="wrapped-card">
                <span className="wrapped-card-label">Passos no ano</span>
                <strong style={{ fontSize: 36 }}>{(data.totals.steps / 1_000_000).toFixed(2)}M</strong>
                <span className="muted">{data.totals.steps.toLocaleString("pt-BR")} passos totais</span>
              </div>
              <div className="wrapped-card">
                <span className="wrapped-card-label">Dias ativos</span>
                <strong style={{ fontSize: 36 }}>
                  {data.totals.active_days}
                  <span style={{ fontSize: 16, color: "var(--muted)" }}> / {data.totals.active_days + data.totals.rest_days}</span>
                </strong>
                <span className="muted">{data.totals.rest_days} dias de descanso</span>
              </div>
              <div className="wrapped-card">
                <span className="wrapped-card-label">Energia total estimada</span>
                <strong style={{ fontSize: 36 }}>{(data.totals.kcal_total_day / 1000).toFixed(0)}k</strong>
                <span className="muted">{data.totals.kcal_total_day.toLocaleString("pt-BR")} kcal · BMR + ativos</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
