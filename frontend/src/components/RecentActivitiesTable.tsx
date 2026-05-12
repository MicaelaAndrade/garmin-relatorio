import { useMemo, useState } from "react";
import type { RecentActivity, Sport } from "../api/client";
import { formatPace, formatTime } from "../api/client";

const SPORT_ICON: Record<Sport, string> = {
  run: "🏃",
  bike: "🚴",
  swim: "🏊",
  yoga: "🧘",
  strength: "💪",
  walking: "🚶",
  other: "•",
};
const SPORT_LABEL: Record<Sport, string> = {
  run: "Corrida",
  bike: "Bike",
  swim: "Nado",
  yoga: "Yoga",
  strength: "Fortalecimento",
  walking: "Caminhada",
  other: "Outro",
};

const DAYS_PER_PAGE = 7;

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function dateKey(iso: string): string {
  return iso.slice(0, 10);
}

function formatDayHeader(yyyymmdd: string): string {
  const d = new Date(yyyymmdd + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today.getTime() - d.getTime()) / 86_400_000);
  const dow = d.toLocaleDateString("pt-BR", { weekday: "long" });
  const fmt = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "long" });
  const prefix = diff === 0 ? "Hoje · " : diff === 1 ? "Ontem · " : "";
  return `${prefix}${dow.charAt(0).toUpperCase()}${dow.slice(1)}, ${fmt}`;
}

function activityUrl(source: string, externalId: string): string | null {
  if (!externalId) return null;
  if (source === "garmin") return `https://connect.garmin.com/modern/activity/${externalId}`;
  if (source === "strava") return `https://www.strava.com/activities/${externalId}`;
  return null;
}

export function RecentActivitiesTable({ data }: { data: RecentActivity[] }) {
  // Agrupa atividades por dia (data calendário), preservando ordem decrescente
  const groupedDays = useMemo(() => {
    const map = new Map<string, RecentActivity[]>();
    for (const a of data) {
      const k = dateKey(a.started_at);
      const arr = map.get(k);
      if (arr) arr.push(a);
      else map.set(k, [a]);
    }
    return Array.from(map.entries()).sort((a, b) => b[0].localeCompare(a[0]));
  }, [data]);

  const totalPages = Math.max(1, Math.ceil(groupedDays.length / DAYS_PER_PAGE));
  const [page, setPage] = useState(0);
  const currentDays = groupedDays.slice(
    page * DAYS_PER_PAGE,
    page * DAYS_PER_PAGE + DAYS_PER_PAGE,
  );
  const firstDay = currentDays[currentDays.length - 1]?.[0];
  const lastDay = currentDays[0]?.[0];

  if (data.length === 0) {
    return (
      <>
        <h2>Últimas atividades</h2>
        <div className="empty">Nenhum treino registrado ainda.</div>
      </>
    );
  }

  return (
    <>
      <div className="activities-head">
        <div>
          <h2 style={{ display: "inline" }}>Últimas atividades</h2>
          {firstDay && lastDay && (
            <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>
              {firstDay === lastDay
                ? formatDayHeader(firstDay)
                : `${formatDayHeader(firstDay)} → ${formatDayHeader(lastDay)}`}
            </span>
          )}
        </div>
        <div className="pager">
          <button
            type="button"
            className="pager-btn"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            title="7 dias anteriores"
          >
            ← anteriores
          </button>
          <span className="pager-info">
            {page + 1}/{totalPages}
          </span>
          <button
            type="button"
            className="pager-btn"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            title="7 dias mais recentes"
          >
            recentes →
          </button>
        </div>
      </div>
      <div className="activity-table">
        <div className="activity-row activity-header">
          <span></span>
          <span>Quando</span>
          <span>Tipo</span>
          <span style={{ textAlign: "right" }}>Distância</span>
          <span style={{ textAlign: "right" }}>Tempo</span>
          <span style={{ textAlign: "right" }}>Pace</span>
          <span style={{ textAlign: "right" }}>FC méd</span>
        </div>
        {currentDays.map(([day, acts]) => (
          <div key={day} className="activity-day-group">
            <div className="activity-day-header">{formatDayHeader(day)}</div>
            {acts.map((a) => {
              const distKm = a.distance_m ? a.distance_m / 1000 : null;
              const label = a.name || SPORT_LABEL[a.sport] || a.sport;
              const href = activityUrl(a.source, a.external_id);
              return (
                <div key={a.id} className="activity-row">
                  <span style={{ fontSize: 18 }}>{SPORT_ICON[a.sport] || "•"}</span>
                  <span className="muted">{formatDate(a.started_at)}</span>
                  <span>
                    {href ? (
                      <a
                        href={href}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="activity-link"
                        title={`Abrir no ${a.source === "garmin" ? "Garmin Connect" : "Strava"}`}
                      >
                        {label}
                      </a>
                    ) : (
                      label
                    )}
                  </span>
                  <span style={{ textAlign: "right" }}>
                    {distKm ? `${distKm.toFixed(2)} km` : "—"}
                  </span>
                  <span style={{ textAlign: "right" }}>{formatTime(a.duration_s)}</span>
                  <span style={{ textAlign: "right" }}>
                    {a.avg_pace_s_km ? formatPace(a.avg_pace_s_km) : "—"}
                  </span>
                  <span style={{ textAlign: "right" }}>
                    {a.avg_hr ? `${a.avg_hr} bpm` : "—"}
                  </span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </>
  );
}
