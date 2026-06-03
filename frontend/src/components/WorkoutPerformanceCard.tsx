import { useState } from "react";
import type {
  LastWorkout,
  SwimMetricRating,
  SwimTechAnalysis,
  SwimTechMetric,
  WorkoutComparison,
  WorkoutZoneBar,
} from "../api/client";

const RATING_COLOR: Record<SwimMetricRating, string> = {
  good: "var(--good, #4ade80)",
  warn: "var(--warn, #fbbf24)",
  bad: "var(--danger, #ef4444)",
  neutral: "var(--muted)",
};
const RATING_ICON: Record<SwimMetricRating, string> = {
  good: "✅",
  warn: "⚠️",
  bad: "❌",
  neutral: "·",
};
const ZONE_COLORS: Record<string, string> = {
  Z1: "#60a5fa",
  Z2: "#4ade80",
  Z3: "#fbbf24",
  Z4: "#fb923c",
  Z5: "#ef4444",
};

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      weekday: "short",
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function MetricList({ metrics }: { metrics: SwimTechMetric[] }) {
  return (
    <div className="swim-tech-metrics">
      {metrics.map((m, i) => (
        <div key={i} className="swim-tech-metric">
          <span className="swim-tech-icon">{RATING_ICON[m.rating]}</span>
          <span className="swim-tech-name">{m.name}</span>
          <span className="swim-tech-value" style={{ color: RATING_COLOR[m.rating] }}>
            {m.value}
          </span>
          <span className="swim-tech-hint muted">— {m.hint}</span>
        </div>
      ))}
    </div>
  );
}

function ZoneBar({ zones }: { zones: WorkoutZoneBar[] }) {
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: "flex", height: 18, borderRadius: 6, overflow: "hidden" }}>
        {zones.map((z) => (
          <div
            key={z.zone}
            title={`${z.zone}: ${z.pct}% (${Math.round(z.secs / 60)}min)`}
            style={{
              width: `${z.pct}%`,
              background: ZONE_COLORS[z.zone] ?? "var(--muted)",
            }}
          />
        ))}
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 6, fontSize: 12 }}>
        {zones.map((z) => (
          <span key={z.zone} style={{ color: ZONE_COLORS[z.zone] ?? "var(--muted)" }}>
            {z.zone} {z.pct}%
          </span>
        ))}
      </div>
    </div>
  );
}

function ComparisonBanner({ c }: { c: WorkoutComparison }) {
  const movedNote =
    c.match_kind === "shifted"
      ? `Casado com o treino de ${c.day_label ?? "outro dia"} (treino movido)`
      : "Treino prescrito pra hoje";
  return (
    <div
      style={{
        marginTop: 12,
        padding: "10px 12px",
        borderRadius: 8,
        background: "var(--card-alt, rgba(255,255,255,0.04))",
        borderLeft: `3px solid ${RATING_COLOR[c.intensity_rating]}`,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600 }}>
        🎯 vs prescrito{c.label ? `: ${c.label}` : ""}
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
        {movedNote}
      </div>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 6, fontSize: 13 }}>
        {c.prescribed_distance_label && (
          <span>
            Distância: {c.prescribed_distance_label}
            {c.distance_pct != null && (
              <strong style={{ marginLeft: 4 }}>({c.distance_pct}%)</strong>
            )}
          </span>
        )}
        {c.prescribed_zone && (
          <span>
            Zona alvo: <strong style={{ color: ZONE_COLORS[c.prescribed_zone] }}>{c.prescribed_zone}</strong>
          </span>
        )}
      </div>
      {c.intensity_note && (
        <div style={{ marginTop: 6, fontSize: 13, color: RATING_COLOR[c.intensity_rating] }}>
          {RATING_ICON[c.intensity_rating]} {c.intensity_note}
        </div>
      )}
    </div>
  );
}

function SwimTechBlock({ tech }: { tech: SwimTechAnalysis }) {
  const [checklistOpen, setChecklistOpen] = useState(false);
  return (
    <div className="swim-tech" style={{ marginTop: 12 }}>
      <div className="swim-tech-head">📊 Análise técnica</div>
      <MetricList metrics={tech.metrics} />
      {tech.tips.length > 0 && (
        <div className="swim-tech-tips">
          <div className="swim-tech-subhead">Pontos pra trabalhar</div>
          <ul>
            {tech.tips.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}
      <button
        type="button"
        className="swim-tech-checklist-toggle"
        onClick={() => setChecklistOpen((v) => !v)}
      >
        {checklistOpen ? "▲" : "▼"} Checklist de técnica
      </button>
      {checklistOpen && (
        <ul className="swim-tech-checklist">
          {tech.checklist.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

const Chip = ({ children }: { children: React.ReactNode }) => (
  <span
    style={{
      padding: "3px 9px",
      borderRadius: 999,
      background: "var(--card-alt, rgba(255,255,255,0.06))",
      fontSize: 13,
      whiteSpace: "nowrap",
    }}
  >
    {children}
  </span>
);

export function WorkoutPerformanceCard({ data }: { data: LastWorkout }) {
  if (!data?.available || !data.header) {
    return (
      <>
        <h2>Desempenho do último treino</h2>
        <p className="muted">Nenhum treino encontrado. Rode o ingest pra trazer a atividade.</p>
      </>
    );
  }
  const h = data.header;
  return (
    <>
      <h2>Desempenho do último treino</h2>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <span style={{ fontSize: 26 }}>{h.icon}</span>
        <div>
          <div style={{ fontWeight: 600 }}>{h.name}</div>
          <div className="muted" style={{ fontSize: 12 }}>
            {formatWhen(h.started_at)}
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {h.distance_label && <Chip>📏 {h.distance_label}</Chip>}
        <Chip>⏱️ {h.duration_label}</Chip>
        {h.pace_label && <Chip>⚡ {h.pace_label}</Chip>}
        {h.avg_hr != null && (
          <Chip>
            ❤️ {h.avg_hr}
            {h.max_hr != null ? ` / ${h.max_hr} máx` : ""} bpm
          </Chip>
        )}
        {h.calories != null && <Chip>🔥 {h.calories} kcal</Chip>}
      </div>

      {data.comparison && <ComparisonBanner c={data.comparison} />}

      {data.zones && data.zones.length > 0 && <ZoneBar zones={data.zones} />}

      {data.swim_tech && <SwimTechBlock tech={data.swim_tech} />}

      {!data.swim_tech && data.metrics && data.metrics.length > 0 && (
        <div className="swim-tech" style={{ marginTop: 12 }}>
          <MetricList metrics={data.metrics} />
        </div>
      )}
    </>
  );
}
