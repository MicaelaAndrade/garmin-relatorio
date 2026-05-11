import type { RaceComparison } from "../api/client";
import { formatPace, formatTime } from "../api/client";

export function RaceComparisonCard({ data }: { data: RaceComparison }) {
  if (data.rows.length === 0) {
    return (
      <>
        <h2>Riegel × Garmin</h2>
        <div className="empty">Sem dados suficientes pra comparar.</div>
      </>
    );
  }

  return (
    <>
      <h2>Riegel × Garmin</h2>
      <div className="label" style={{ marginBottom: 12 }}>
        Comparação entre fórmula clássica (Riegel) e predição do seu relógio (FirstBeat usa VO2max).
      </div>
      <div className="comparison">
        <div className="cmp-row cmp-header">
          <span></span>
          <span>Riegel</span>
          <span>Garmin</span>
          <span style={{ textAlign: "right" }}>Δ</span>
        </div>
        {data.rows.map((r) => (
          <div key={r.distance_m} className="cmp-row">
            <span className="cmp-label">{r.label}</span>
            <span>
              {r.riegel_s ? formatTime(r.riegel_s) : "—"}
              {r.riegel_pace && <span className="muted"> · {formatPace(r.riegel_pace)}</span>}
            </span>
            <span>
              {r.garmin_s ? formatTime(r.garmin_s) : "—"}
              {r.garmin_pace && <span className="muted"> · {formatPace(r.garmin_pace)}</span>}
            </span>
            <span
              style={{
                textAlign: "right",
                color: r.diff_s === null ? "var(--muted)" : r.diff_s > 0 ? "var(--warn)" : "var(--accent)",
              }}
            >
              {r.diff_s === null
                ? "—"
                : r.diff_s === 0
                  ? "0s"
                  : `${r.diff_s > 0 ? "+" : ""}${formatTime(Math.abs(r.diff_s))}`}
            </span>
          </div>
        ))}
      </div>
      {data.riegel_reference && (
        <div className="label" style={{ marginTop: 12 }}>
          Riegel base: {(data.riegel_reference.distance_m / 1000).toFixed(1)}km em{" "}
          {formatTime(data.riegel_reference.duration_s)}
        </div>
      )}
    </>
  );
}
