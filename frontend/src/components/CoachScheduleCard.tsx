import { useState } from "react";
import type { CoachSchedule, CoachToday, CoachWorkout, WorkoutBlock } from "../api/client";

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

function WorkoutPill({ w }: { w: CoachWorkout }) {
  const [expanded, setExpanded] = useState(false);
  const color = KIND_COLOR[w.kind] || "#8b96a8";
  const hasStructure = w.has_structure && w.blocks.length > 0;
  return (
    <div className={`coach-pill${hasStructure ? " coach-pill-clickable" : ""}`}>
      <div
        className="coach-pill-head"
        onClick={hasStructure ? () => setExpanded((v) => !v) : undefined}
        title={hasStructure ? "Clique pra ver a estrutura do treino" : w.label}
      >
        <span className="coach-pill-icon">{w.icon}</span>
        <span className="coach-pill-label" style={{ color }}>{w.label}</span>
        <div className="coach-pill-meta">
          {w.duration_min > 0 && <span className="coach-pill-dur">{w.duration_min}min</span>}
          {w.zone && <span className="coach-pill-zone" style={{ color }}>{w.zone}</span>}
          {hasStructure && <span className="coach-pill-toggle">{expanded ? "▲" : "▼"}</span>}
        </div>
      </div>
      {expanded && hasStructure && (
        <div className="coach-pill-blocks">
          {w.blocks.map((b, i) => (
            <StepRow key={i} b={b} />
          ))}
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
