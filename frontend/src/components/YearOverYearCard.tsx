import type { YearOverYear } from "../api/client";
import { formatPace } from "../api/client";

const SPORT_ICON: Record<string, string> = {
  run: "🏃",
  bike: "🚴",
  swim: "🏊",
  strength: "💪",
  yoga: "🧘",
  walking: "🚶",
};

function deltaText(now: number, then: number, unit = ""): { label: string; color: string } {
  if (then === 0 && now === 0) return { label: "—", color: "var(--muted)" };
  if (then === 0) return { label: `novo${unit ? " " + unit : ""}`, color: "var(--accent)" };
  const diff = now - then;
  const pct = (diff / then) * 100;
  const sign = diff > 0 ? "+" : "";
  const color = diff > 0 ? "var(--accent)" : diff < 0 ? "var(--warn)" : "var(--muted)";
  return { label: `${sign}${diff.toFixed(unit === "%" ? 1 : 1)}${unit} (${sign}${pct.toFixed(0)}%)`, color };
}

export const YOY_MIN_SESSIONS = 3;

export function isYearOverYearAvailable(data: YearOverYear): boolean {
  return Boolean(
    data.available
    && data.this_period
    && data.last_period
    && data.deltas
    && data.last_period.sessions >= YOY_MIN_SESSIONS,
  );
}

export function YearOverYearCard({ data }: { data: YearOverYear }) {
  if (!data.available || !data.this_period || !data.last_period || !data.deltas) {
    return (
      <>
        <h2>Você × Você (ano passado)</h2>
        <div className="empty">Sem dados suficientes para comparação ano-a-ano.</div>
      </>
    );
  }
  const t = data.this_period;
  const l = data.last_period;

  return (
    <>
      <h2>Você × Você (ano passado)</h2>
      <div className="muted" style={{ fontSize: 11, marginBottom: 12 }}>
        Mês corrente ({t.label}) comparado com mesmo período em {l.label}
      </div>

      <div className="yoy-grid">
        <div className="yoy-cell">
          <span className="yoy-label">Sessões</span>
          <div className="yoy-vs">
            <span className="yoy-now">{t.sessions}</span>
            <span className="yoy-vs-sep">vs</span>
            <span className="yoy-then">{l.sessions}</span>
          </div>
          <span className="yoy-delta" style={{ color: deltaText(t.sessions, l.sessions).color }}>
            {deltaText(t.sessions, l.sessions).label}
          </span>
        </div>
        <div className="yoy-cell">
          <span className="yoy-label">Distância</span>
          <div className="yoy-vs">
            <span className="yoy-now">{t.distance_km.toFixed(1)}<small>km</small></span>
            <span className="yoy-vs-sep">vs</span>
            <span className="yoy-then">{l.distance_km.toFixed(1)}<small>km</small></span>
          </div>
          <span className="yoy-delta" style={{ color: deltaText(t.distance_km, l.distance_km, "km").color }}>
            {deltaText(t.distance_km, l.distance_km, "km").label}
          </span>
        </div>
        <div className="yoy-cell">
          <span className="yoy-label">Duração</span>
          <div className="yoy-vs">
            <span className="yoy-now">{Math.round(t.duration_min / 60)}<small>h</small></span>
            <span className="yoy-vs-sep">vs</span>
            <span className="yoy-then">{Math.round(l.duration_min / 60)}<small>h</small></span>
          </div>
          <span className="yoy-delta" style={{ color: deltaText(t.duration_min, l.duration_min, "min").color }}>
            {deltaText(t.duration_min, l.duration_min, "min").label}
          </span>
        </div>
        <div className="yoy-cell">
          <span className="yoy-label">Calorias</span>
          <div className="yoy-vs">
            <span className="yoy-now">{t.kcal.toLocaleString("pt-BR")}</span>
            <span className="yoy-vs-sep">vs</span>
            <span className="yoy-then">{l.kcal.toLocaleString("pt-BR")}</span>
          </div>
          <span className="yoy-delta" style={{ color: deltaText(t.kcal, l.kcal, "kcal").color }}>
            {deltaText(t.kcal, l.kcal, " kcal").label}
          </span>
        </div>
      </div>

      {data.by_sport_compare && data.by_sport_compare.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="label" style={{ marginBottom: 6 }}>Por modalidade</div>
          <div className="yoy-table">
            <div className="yoy-row yoy-row-header">
              <span></span>
              <span>Modalidade</span>
              <span>Sessões</span>
              <span>Distância</span>
              <span>Pace</span>
            </div>
            {data.by_sport_compare.map((s) => {
              const dist = deltaText(s.this_distance_km, s.last_distance_km, "km");
              const sess = deltaText(s.this_sessions, s.last_sessions, "");
              const paceDelta = s.pace_delta_s;
              const paceColor =
                paceDelta == null ? "var(--muted)" : paceDelta < 0 ? "var(--accent)" : "var(--warn)";
              return (
                <div key={s.sport} className="yoy-row">
                  <span style={{ fontSize: 16 }}>{SPORT_ICON[s.sport] || "•"}</span>
                  <span className="yoy-sport-name">{s.label}</span>
                  <span>
                    <span className="yoy-now-small">{s.this_sessions}</span>
                    <span className="muted"> vs {s.last_sessions} </span>
                    <span style={{ color: sess.color, fontSize: 10 }}>({sess.label.split(" ")[0]})</span>
                  </span>
                  <span>
                    <span className="yoy-now-small">{s.this_distance_km.toFixed(1)}</span>
                    <span className="muted"> vs {s.last_distance_km.toFixed(1)} </span>
                    <span style={{ color: dist.color, fontSize: 10 }}>({dist.label.split(" ")[0]})</span>
                  </span>
                  <span>
                    {s.this_pace_s_km && s.last_pace_s_km ? (
                      <>
                        <span className="yoy-now-small">{formatPace(s.this_pace_s_km)}</span>
                        <span className="muted"> vs {formatPace(s.last_pace_s_km)} </span>
                        {paceDelta !== null && (
                          <span style={{ color: paceColor, fontSize: 10 }}>
                            ({paceDelta > 0 ? "+" : ""}{paceDelta}s)
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
