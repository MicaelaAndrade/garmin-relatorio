import type { CalendarDay } from "../api/client";

/**
 * Heatmap estilo GitHub: colunas = semanas, linhas = dia da semana (seg-dom).
 * Cor = intensidade da carga TRIMP do dia.
 */
function intensityColor(load: number, max: number): string {
  if (load === 0) return "var(--border)";
  const ratio = Math.min(1, load / max);
  if (ratio < 0.2) return "rgba(74, 222, 128, 0.25)";
  if (ratio < 0.4) return "rgba(74, 222, 128, 0.5)";
  if (ratio < 0.6) return "rgba(251, 191, 36, 0.6)";
  if (ratio < 0.8) return "rgba(251, 146, 60, 0.75)";
  return "rgba(239, 68, 68, 0.9)";
}

const MONTHS_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

export function CalendarHeatmap({ data }: { data: CalendarDay[] }) {
  if (data.length === 0) {
    return (
      <>
        <h2>Calendário de carga</h2>
        <div className="empty">Sem dados.</div>
      </>
    );
  }

  const max = Math.max(...data.map((d) => d.load));

  // Agrupa em colunas semanais. Cada coluna = 7 dias (seg-dom).
  const start = new Date(data[0].day);
  const startWeekday = (start.getDay() + 6) % 7; // dom=0 -> seg=0
  const padded: (CalendarDay | null)[] = Array(startWeekday).fill(null);
  padded.push(...data);

  const cols: (CalendarDay | null)[][] = [];
  for (let i = 0; i < padded.length; i += 7) {
    cols.push(padded.slice(i, i + 7));
  }

  // Estatísticas pra header
  const weekCount = cols.length;
  const activeDays = data.filter((d) => d.sessions > 0).length;
  const totalSessions = data.reduce((s, d) => s + d.sessions, 0);
  const totalMin = data.reduce((s, d) => s + d.duration_min, 0);

  // Mes label: aparece sobre a 1a coluna do mes
  const monthLabels = cols.map((col) => {
    const firstDay = col.find((d) => d !== null);
    if (!firstDay) return "";
    const date = new Date(firstDay.day);
    return date.getDate() <= 7 ? MONTHS_PT[date.getMonth()] : "";
  });

  return (
    <>
      <div className="cal-head">
        <h2 style={{ display: "inline" }}>Calendário de carga</h2>
        <span className="cal-subtitle">
          últimas <strong>{weekCount}</strong> semanas · {activeDays} dias com treino · {totalSessions} sessões · {Math.round(totalMin / 60)}h totais
        </span>
      </div>
      <div className="calendar-gh">
        <div className="cal-months">
          <span className="cal-spacer" />
          {monthLabels.map((m, i) => (
            <span key={i} className="cal-month-label">{m}</span>
          ))}
        </div>
        <div className="cal-body">
          <div className="cal-weekdays">
            <span></span>
            <span>Seg</span>
            <span></span>
            <span>Qua</span>
            <span></span>
            <span>Sex</span>
            <span></span>
          </div>
          <div className="cal-grid">
            {cols.map((col, ci) => (
              <div key={ci} className="cal-col">
                {col.map((day, di) =>
                  day ? (
                    <div
                      key={di}
                      className="cal-cell"
                      style={{ background: intensityColor(day.load, max) }}
                      title={`${day.day} · ${day.sessions} treino(s) · ${day.duration_min}min · load ${day.load.toFixed(0)}${day.sports ? ` (${day.sports})` : ""}`}
                    />
                  ) : (
                    <div key={di} className="cal-cell cal-empty" />
                  ),
                )}
              </div>
            ))}
          </div>
        </div>
        <div className="cal-legend">
          <span className="muted">menos</span>
          {[0, 0.2, 0.4, 0.6, 0.8, 1].map((r) => (
            <div key={r} className="cal-cell" style={{ background: intensityColor(r * max, max) }} />
          ))}
          <span className="muted">mais</span>
        </div>
      </div>
    </>
  );
}
