import { useState } from "react";
import type {
  CoachSchedule,
  CoachToday,
  CoachWorkout,
  SwimMetricRating,
  SwimTechAnalysis,
  WorkoutBlock,
} from "../api/client";

const SWIM_RATING_COLOR: Record<SwimMetricRating, string> = {
  good: "var(--good, #4ade80)",
  warn: "var(--warn, #fbbf24)",
  bad: "var(--danger, #ef4444)",
  neutral: "var(--muted)",
};
const SWIM_RATING_ICON: Record<SwimMetricRating, string> = {
  good: "✅",
  warn: "⚠️",
  bad: "❌",
  neutral: "·",
};

function SwimTechBlock({ tech }: { tech: SwimTechAnalysis }) {
  const [checklistOpen, setChecklistOpen] = useState(false);
  return (
    <div className="swim-tech">
      <div className="swim-tech-head">📊 Análise técnica</div>
      <div className="swim-tech-metrics">
        {tech.metrics.map((m, i) => (
          <div key={i} className="swim-tech-metric">
            <span className="swim-tech-icon">{SWIM_RATING_ICON[m.rating]}</span>
            <span className="swim-tech-name">{m.name}</span>
            <span className="swim-tech-value" style={{ color: SWIM_RATING_COLOR[m.rating] }}>
              {m.value}
            </span>
            <span className="swim-tech-hint muted">— {m.hint}</span>
          </div>
        ))}
      </div>
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

const KIND_COLOR: Record<string, string> = {
  long: "#4ade80",
  tempo: "#fbbf24",
  intervals: "#ef4444",
  fartlek: "#fb923c",
  easy: "#60a5fa",
  tech: "#a78bfa",
  race: "#ef4444",
  workout: "#8b96a8",
};

const ZONE_COLOR: Record<string, string> = {
  Z1: "#60a5fa",
  Z2: "#60a5fa",
  Z3: "#fbbf24",
  Z4: "#ef4444",
  Z5: "#ef4444",
};

function StepRow({ b, depth = 0 }: { b: WorkoutBlock; depth?: number }) {
  if (b.block_type === "repeat") {
    const totalMin = Math.round(b.duration_s / 60);
    return (
      <div className="step-repeat">
        <div className="step-repeat-head">
          <span className="step-repeat-count">{b.count}×</span>
          <span className="muted">({totalMin}min)</span>
        </div>
        <div className="step-repeat-children">
          {b.children.map((child, i) => (
            <StepRow key={i} b={child} depth={depth + 1} />
          ))}
        </div>
      </div>
    );
  }
  const zoneColor = b.zone ? ZONE_COLOR[b.zone] || "var(--muted)" : "var(--muted)";
  return (
    <div className="step-row">
      <span className="step-end">{b.count > 1 ? `${b.count}× ` : ""}{b.end_label}</span>
      <span className="step-kind muted">{b.kind}</span>
      {b.zone && <span className="step-zone" style={{ color: zoneColor }}>{b.zone}</span>}
      {b.pace && <span className="step-pace muted">@ {b.pace}</span>}
    </div>
  );
}

const STATUS_COLOR: Record<string, string> = {
  completo: "#4ade80",
  quase: "#a3e635",
  parcial: "#fbbf24",
  iniciado: "#fb923c",
  executado: "#60a5fa",
};

function WorkoutPill({ w }: { w: CoachWorkout }) {
  const hasStructure = w.has_structure && w.blocks.length > 0;
  const hasExecution = !!w.executed;
  const hasFueling = !!w.fueling;
  const canExpand = hasStructure || hasExecution || hasFueling;
  const [expanded, setExpanded] = useState(hasExecution); // se já tem execução, abre por padrão

  const color = KIND_COLOR[w.kind] || "#8b96a8";
  const e = w.executed;
  const f = w.fueling;

  return (
    <div className={`coach-pill${canExpand ? " coach-pill-clickable" : ""}`}>
      <div
        className="coach-pill-head"
        onClick={canExpand ? () => setExpanded((v) => !v) : undefined}
        title={canExpand ? "Clique pra ver detalhes" : w.label}
      >
        <span className="coach-pill-icon">{w.icon}</span>
        <span className="coach-pill-label" style={{ color }}>
          {e && <span style={{ marginRight: 4 }}>✅</span>}
          {w.label}
        </span>
        <div className="coach-pill-meta">
          {w.duration_min > 0 && <span className="coach-pill-dur">{w.duration_min}min</span>}
          {w.zone && <span className="coach-pill-zone" style={{ color }}>{w.zone}</span>}
          {e && (
            <span
              className="coach-pill-status"
              style={{ color: STATUS_COLOR[e.status] || "var(--accent)" }}
            >
              {e.completion_pct != null ? `${e.completion_pct}%` : "feito"}
            </span>
          )}
          {canExpand && <span className="coach-pill-toggle">{expanded ? "▲" : "▼"}</span>}
        </div>
      </div>
      {expanded && (
        <div className="coach-pill-blocks">
          {e && (
            <div className="coach-execution">
              <div className="coach-execution-head" style={{ color: STATUS_COLOR[e.status] }}>
                ✅ {e.status_label}
                {e.completion_pct != null && ` · ${e.completion_pct}% do prescrito`}
              </div>
              {e.notes.map((n, i) => (
                <div key={i} className="coach-execution-note">{n}</div>
              ))}
              {e.source === "garmin" && e.external_id && (
                <a
                  href={`https://connect.garmin.com/modern/activity/${e.external_id}`}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="coach-execution-link"
                >
                  Abrir no Garmin Connect ↗
                </a>
              )}
              {e.swim_tech && <SwimTechBlock tech={e.swim_tech} />}
            </div>
          )}
          {f && (
            <div className="coach-fueling">
              <div className="coach-fueling-head">
                🥤 Fueling & estratégia · duração estimada <strong>{f.duration_label}</strong>
              </div>
              <div className="coach-fueling-grid">
                <div className="coach-fueling-stat">
                  <span className="cal-stat-label">Hidratação</span>
                  <span className="cal-stat-value" style={{ color: "var(--info)" }}>{f.fluid_total_ml}</span>
                  <span className="cal-stat-unit">ml total · {f.fluid_ml_per_h} ml/h</span>
                </div>
                <div className="coach-fueling-stat">
                  <span className="cal-stat-label">Carbo</span>
                  <span className="cal-stat-value" style={{ color: "var(--warn)" }}>{f.carbs_total_g}</span>
                  <span className="cal-stat-unit">g total · {f.carbs_g_per_h} g/h</span>
                </div>
                <div className="coach-fueling-stat">
                  <span className="cal-stat-label">Sódio</span>
                  <span className="cal-stat-value">{f.sodium_mg_per_h}</span>
                  <span className="cal-stat-unit">mg/h</span>
                </div>
                {f.pace_alvo_label && (
                  <div className="coach-fueling-stat">
                    <span className="cal-stat-label">Pace alvo</span>
                    <span className="cal-stat-value" style={{ color: "var(--accent)" }}>{f.pace_alvo_label}</span>
                    <span className="cal-stat-unit">média</span>
                  </div>
                )}
                {f.speed_alvo_label && (
                  <div className="coach-fueling-stat">
                    <span className="cal-stat-label">Vel. alvo</span>
                    <span className="cal-stat-value" style={{ color: "var(--accent)" }}>{f.speed_alvo_label}</span>
                    <span className="cal-stat-unit">média</span>
                  </div>
                )}
              </div>
              <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>{f.carbs_message}</div>
            </div>
          )}
          {hasStructure && (
            <>
              <div className="label" style={{ marginTop: 8, marginBottom: 4 }}>Estrutura do treino</div>
              {w.blocks.map((b, i) => <StepRow key={i} b={b} />)}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function weekStartLabel(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

function todayIdx(weekStartIso: string): number {
  const start = new Date(weekStartIso + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.floor((today.getTime() - start.getTime()) / 86_400_000);
}

export function CoachScheduleCard({
  schedule,
  today,
}: {
  schedule: CoachSchedule;
  today: CoachToday;
}) {
  if (!schedule.available) {
    return (
      <>
        <h2>Treinos prescritos (coach)</h2>
        <div className="empty">
          Nenhum treino prescrito encontrado para esta semana.
          <div className="label" style={{ marginTop: 8 }}>
            Rode <code>uv run garmin-relatorio ingest-garmin --what scheduled</code> ou aguarde o coach cadastrar.
          </div>
        </div>
      </>
    );
  }

  const todayIndex = todayIdx(schedule.week_start);

  return (
    <>
      <div className="coach-head">
        <div>
          <h2 style={{ display: "inline" }}>Treinos prescritos (coach)</h2>
          <span className="coach-source">via Treius / Garmin Connect</span>
        </div>
        <span className="muted" style={{ fontSize: 12 }}>Semana de {weekStartLabel(schedule.week_start)}</span>
      </div>

      {today.workouts.length > 0 && (
        <div className="coach-today">
          <span className="coach-today-tag">HOJE</span>
          <div className="coach-today-list">
            {today.workouts.map((w, i) => (
              <WorkoutPill key={i} w={w} />
            ))}
          </div>
        </div>
      )}

      {schedule.load_comparison.pct_of_last_week != null && (
        <div className="plan-load" style={{ marginBottom: 14 }}>
          <div
            className="plan-load-num"
            style={{
              color:
                schedule.load_comparison.pct_of_last_week > 130
                  ? "var(--danger)"
                  : schedule.load_comparison.pct_of_last_week > 110
                  ? "var(--warn)"
                  : schedule.load_comparison.pct_of_last_week >= 85
                  ? "var(--accent)"
                  : "var(--info)",
            }}
          >
            {schedule.load_comparison.pct_of_last_week}%
          </div>
          <div className="plan-load-meta">
            <div>carga prescrita vs semana passada</div>
            <div className="muted" style={{ fontSize: 11 }}>
              {schedule.load_comparison.message} (TRIMP {schedule.load_comparison.prescribed_trimp.toFixed(0)} vs {schedule.load_comparison.last_week_trimp.toFixed(0)})
            </div>
          </div>
        </div>
      )}

      <div className="plan-intensity" style={{ marginBottom: 14 }}>
        <div className="label" style={{ marginBottom: 4 }}>
          Distribuição de intensidade prescrita
          <span className="muted" style={{ marginLeft: 6, fontSize: 10 }}>
            (estimativa baseada no tipo de cada treino)
          </span>
        </div>
        <div className="plan-bar">
          <span className="plan-bar-seg low" style={{ flex: schedule.intensity_mix.low }} title={`Z1-Z2: ${schedule.intensity_mix.low}%`} />
          <span className="plan-bar-seg mid" style={{ flex: schedule.intensity_mix.mid }} title={`Z3: ${schedule.intensity_mix.mid}%`} />
          <span className="plan-bar-seg high" style={{ flex: schedule.intensity_mix.high }} title={`Z4-Z5: ${schedule.intensity_mix.high}%`} />
        </div>
        <div className="plan-bar-legend">
          <span>Z1-Z2 {schedule.intensity_mix.low}%</span>
          <span>Z3 {schedule.intensity_mix.mid}%</span>
          <span>Z4-Z5 {schedule.intensity_mix.high}%</span>
        </div>
      </div>

      <div className="coach-grid">
        {schedule.days.map((d) => {
          const isToday = d.day_idx === todayIndex;
          const isPast = todayIndex >= 0 && d.day_idx < todayIndex;
          return (
            <div
              key={d.day_idx}
              className={`coach-day${isToday ? " coach-day-today" : ""}${isPast ? " coach-day-past" : ""}`}
            >
              <div className="coach-dow">{d.day_label}</div>
              {d.workouts.length === 0 ? (
                <div className="coach-empty">—</div>
              ) : (
                d.workouts.map((w, i) => <WorkoutPill key={i} w={w} />)
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
