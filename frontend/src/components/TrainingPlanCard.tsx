import type { TrainingPlan, TrainingPlanDay } from "../api/client";

const KIND_COLOR: Record<string, string> = {
  long: "#4ade80",
  long_aerobic: "#4ade80",
  long_easy: "#4ade80",
  tempo: "#fbbf24",
  intervals: "#ef4444",
  race_pace: "#fbbf24",
  race_simulation: "#fbbf24",
  race: "#ef4444",
  shake_out: "#60a5fa",
  easy: "#60a5fa",
  tech: "#a78bfa",
  rest: "#8b96a8",
};

function ScheduleDay({ day }: { day: TrainingPlanDay }) {
  const isRest = day.kind === "rest";
  const isRace = day.kind === "race";
  const color = KIND_COLOR[day.kind || "rest"] || "#8b96a8";
  return (
    <div className={`sched-day${isRest ? " sched-rest" : ""}${isRace ? " sched-race" : ""}`}>
      <div className="sched-dow">{day.day_label}</div>
      <div className="sched-icon">{day.icon || "·"}</div>
      <div className="sched-label" style={{ color }}>{day.label || "—"}</div>
      {!isRest && day.duration_min > 0 && (
        <div className="sched-dur">{Math.round(day.duration_min)}min</div>
      )}
      {day.distance_km != null && day.distance_km > 0 && (
        <div className="sched-dist">{day.distance_km.toFixed(1)}km</div>
      )}
      {day.zone && <div className="sched-zone" style={{ color }}>{day.zone}</div>}
      {day.target && (
        <div className="sched-target" title={day.target}>{day.target}</div>
      )}
    </div>
  );
}

const SPORT_ICON: Record<string, string> = { run: "🏃", bike: "🚴", swim: "🏊" };
const SPORT_LABEL: Record<string, string> = { run: "Corrida", bike: "Bike", swim: "Nado" };
const PHASE_LABEL: Record<TrainingPlan["phase"], string> = {
  base: "Base",
  build: "Build",
  peak: "Peak",
  taper: "Taper",
  race_week: "Semana da prova",
  manutencao: "Manutenção",
};
const PHASE_COLOR: Record<TrainingPlan["phase"], string> = {
  base: "#60a5fa",
  build: "#4ade80",
  peak: "#fbbf24",
  taper: "#fb923c",
  race_week: "#ef4444",
  manutencao: "#8b96a8",
};

function loadColor(pct: number): string {
  if (pct < 80) return "var(--danger)";
  if (pct < 95) return "var(--warn)";
  if (pct <= 110) return "var(--accent)";
  return "var(--info)";
}

function formatWeekStart(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

export function TrainingPlanCard({ plan }: { plan: TrainingPlan }) {
  const totalMin = plan.sessions_by_sport.reduce((s, x) => s + x.duration_min, 0);
  const totalSessions = plan.sessions_by_sport.reduce((s, x) => s + x.sessions, 0);

  return (
    <>
      <div className="plan-title-row">
        <h2>Sugestão automática (próxima semana)</h2>
        <span className="muted" style={{ fontSize: 11 }}>baseado em ACWR + overtraining, não prescrito</span>
      </div>
      <div className="plan-head">
        <div>
          <div className="plan-week">Semana de {formatWeekStart(plan.week_start)}</div>
          <div className="muted" style={{ fontSize: 12 }}>{plan.phase_reason}</div>
        </div>
        <span
          className="zone"
          style={{ background: `${PHASE_COLOR[plan.phase]}33`, color: PHASE_COLOR[plan.phase] }}
        >
          {PHASE_LABEL[plan.phase]}
        </span>
      </div>

      <div className="plan-load">
        <div className="plan-load-num" style={{ color: loadColor(plan.target_load_pct) }}>
          {plan.target_load_pct}%
        </div>
        <div className="plan-load-meta">
          <div>da carga da semana passada</div>
          <div className="muted" style={{ fontSize: 11 }}>{plan.target_reason}</div>
        </div>
      </div>

      <div className="plan-totals">
        <div><strong>{totalSessions}</strong> sessões</div>
        <div><strong>{Math.round(totalMin)}</strong> min</div>
        <div><strong>{plan.rest_days}</strong> dia{plan.rest_days === 1 ? "" : "s"} de descanso</div>
      </div>

      <div className="plan-sports">
        {plan.sessions_by_sport.map((s) => (
          <div key={s.sport} className="plan-sport-row">
            <span style={{ fontSize: 18 }}>{SPORT_ICON[s.sport] || "•"}</span>
            <span>{SPORT_LABEL[s.sport] || s.sport}</span>
            <span className="muted">{s.sessions}×</span>
            <span style={{ textAlign: "right" }}>{Math.round(s.duration_min)} min</span>
            <span style={{ textAlign: "right" }}>{s.distance_km.toFixed(1)} km</span>
          </div>
        ))}
      </div>

      {plan.schedule && plan.schedule.length === 7 && (
        <div className="plan-schedule">
          <div className="label" style={{ marginBottom: 6 }}>
            Como o algoritmo distribuiria — para comparar com o que o coach mandou
          </div>
          <div className="sched-grid">
            {plan.schedule.map((d) => (
              <ScheduleDay key={d.day_idx} day={d} />
            ))}
          </div>
        </div>
      )}

      <div className="plan-intensity">
        <div className="label" style={{ marginBottom: 4 }}>Distribuição de intensidade sugerida</div>
        <div className="plan-bar">
          <span className="plan-bar-seg low" style={{ flex: plan.intensity_mix.low }} title={`Z1-Z2: ${plan.intensity_mix.low}%`} />
          <span className="plan-bar-seg mid" style={{ flex: plan.intensity_mix.mid }} title={`Z3: ${plan.intensity_mix.mid}%`} />
          <span className="plan-bar-seg high" style={{ flex: plan.intensity_mix.high }} title={`Z4-Z5: ${plan.intensity_mix.high}%`} />
        </div>
        <div className="plan-bar-legend">
          <span>Z1-Z2 {plan.intensity_mix.low}%</span>
          <span>Z3 {plan.intensity_mix.mid}%</span>
          <span>Z4-Z5 {plan.intensity_mix.high}%</span>
        </div>
      </div>

      {plan.key_sessions.length > 0 && (
        <div className="plan-key">
          <div className="label" style={{ marginBottom: 4 }}>Sessões-chave</div>
          {plan.key_sessions.map((k, i) => (
            <div key={i} className="plan-key-row">
              <strong>{k.label}</strong>
              <div className="muted" style={{ fontSize: 12 }}>{k.target}</div>
            </div>
          ))}
        </div>
      )}

      {plan.warnings.length > 0 && (
        <div className="plan-warnings">
          {plan.warnings.map((w, i) => (
            <div key={i} className="plan-warn">⚠ {w}</div>
          ))}
        </div>
      )}
    </>
  );
}
