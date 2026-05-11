import type { OvertrainingStatus } from "../api/client";

const FLAG_LABEL = {
  ok: "OK",
  atencao: "Atenção",
  alerta: "Alerta",
  vermelho: "Vermelho",
} as const;

const FLAG_COLOR = {
  ok: "#4ade80",
  atencao: "#fbbf24",
  alerta: "#fb923c",
  vermelho: "#ef4444",
} as const;

export function OvertrainingCard({ data }: { data: OvertrainingStatus }) {
  return (
    <>
      <h2>Overtraining</h2>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 4 }}>
        <span className="big">
          {data.score}
          <span className="label" style={{ fontSize: 16, marginLeft: 4 }}>/{data.max_score}</span>
        </span>
        <span
          className="zone"
          style={{ background: `${FLAG_COLOR[data.flag]}33`, color: FLAG_COLOR[data.flag] }}
        >
          {FLAG_LABEL[data.flag]}
        </span>
      </div>
      <div className="label">Sinais detectados nas últimas 7-28 noites</div>
      <p className="recommendation">{data.message}</p>
      {data.signals.length > 0 && (
        <ul className="notes">
          {data.signals.map((s) => (
            <li key={s.kind}>⚠ {s.msg}</li>
          ))}
        </ul>
      )}
      <div className="ot-metrics">
        {data.hrv && (
          <div className="ot-metric">
            <div className="label">HRV (3d / baseline)</div>
            <div>
              <strong>{data.hrv.last_3_avg.toFixed(0)}</strong>{" "}
              <span className="muted">/ {data.hrv.baseline_avg.toFixed(0)} ms</span>
            </div>
          </div>
        )}
        {data.rhr && (
          <div className="ot-metric">
            <div className="label">FC repouso (3d / baseline)</div>
            <div>
              <strong>{data.rhr.last_3_avg.toFixed(0)}</strong>{" "}
              <span className="muted">/ {data.rhr.baseline_avg.toFixed(0)} bpm</span>
            </div>
          </div>
        )}
        {data.sleep && (
          <div className="ot-metric">
            <div className="label">Sono (7d)</div>
            <div>
              <strong>
                {data.sleep.avg_total_min ? (data.sleep.avg_total_min / 60).toFixed(1) : "—"}h
              </strong>
              {data.sleep.avg_score && (
                <span className="muted"> · score {data.sleep.avg_score.toFixed(0)}</span>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
