import type { PerformancePrediction } from "../api/client";
import { formatDistance, formatPace, formatTime } from "../api/client";

const SPORT_LABEL: Record<string, string> = { run: "Corrida", swim: "Natação", bike: "Ciclismo" };

export function PerformanceCard({ predictions }: { predictions: Record<string, PerformancePrediction> }) {
  const hasAny = Object.values(predictions).some((p) => p.predictions.length > 0);
  if (!hasAny) {
    return (
      <>
        <h2>Predição de performance (Riegel)</h2>
        <div className="empty">Sem treinos suficientes para projetar provas.</div>
      </>
    );
  }
  return (
    <>
      <h2>Predição de performance (Riegel)</h2>
      {Object.entries(predictions).map(([sport, pred]) => {
        if (pred.predictions.length === 0) return null;
        return (
          <div key={sport} style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 14, marginBottom: 4 }}>{SPORT_LABEL[sport] || sport}</h3>
            {pred.reference && (
              <div className="label" style={{ marginBottom: 6 }}>
                Base: {formatDistance(pred.reference.distance_m)} em {formatTime(pred.reference.duration_s)} ({formatPace(pred.reference.pace_s_km)})
              </div>
            )}
            <div className="predictions">
              {pred.predictions.map((p) => (
                <div key={p.distance_m} className="pred-row">
                  <span>{formatDistance(p.distance_m)}</span>
                  <span>{formatTime(p.predicted_time_s)} <span className="label">({formatPace(p.predicted_pace_s_km)})</span></span>
                  <span className={`conf ${p.confidence}`}>{p.confidence}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </>
  );
}
