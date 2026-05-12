import type { VdotDashboard } from "../api/client";
import { formatPace } from "../api/client";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

const PACE_COLOR: Record<string, string> = {
  easy: "#60a5fa",
  marathon: "#4ade80",
  threshold: "#fbbf24",
  interval: "#fb923c",
  repetition: "#ef4444",
};

export function VdotCard({ data }: { data: VdotDashboard }) {
  if (!data.available || !data.vdot) {
    return (
      <>
        <h2>VDOT (Daniels) · paces de treino</h2>
        <div className="empty">{data.reason || "Sem dados suficientes."}</div>
      </>
    );
  }
  const b = data.based_on!;
  return (
    <>
      <h2>VDOT (Daniels) · paces de treino</h2>
      <div className="muted" style={{ fontSize: 11, marginBottom: 12 }}>
        Estima VO2max equivalente e prescreve paces de treino baseado na sua melhor performance recente.
      </div>

      <div className="cal-stats" style={{ marginBottom: 14 }}>
        <div className="cal-stat" title="VO2max equivalente segundo Jack Daniels. Compare com VO2max do Garmin pra cross-check.">
          <span className="cal-stat-label">VDOT atual</span>
          <span className="cal-stat-value" style={{ color: "var(--accent)" }}>{data.vdot}</span>
          <span className="cal-stat-unit">ml/kg/min equivalente</span>
        </div>
        <div className="cal-stat">
          <span className="cal-stat-label">Baseado em</span>
          <span className="cal-stat-value">{b.distance_km}<small style={{ fontSize: 12, color: "var(--muted)" }}>km</small></span>
          <span className="cal-stat-unit">
            {formatTime(b.duration_s)} · {b.pace_s_km ? formatPace(b.pace_s_km) : "—"} · {formatDate(b.started_at)}
          </span>
        </div>
      </div>

      <div className="vdot-paces">
        {data.paces?.map((p) => (
          <div key={p.key} className="vdot-pace-row" style={{ borderLeftColor: PACE_COLOR[p.key] || "var(--info)" }}>
            <div className="vdot-pace-head">
              <span className="vdot-pace-label" style={{ color: PACE_COLOR[p.key] }}>{p.label}</span>
              <span className="vdot-pace-pct">{p.pct_vdot}%</span>
              <span className="vdot-pace-value">{formatPace(p.pace_s_km)}</span>
            </div>
            <div className="vdot-pace-desc">{p.description}</div>
          </div>
        ))}
      </div>

      <div className="cal-note" style={{ marginTop: 12 }}>
        💡 Esses paces são <strong>referência</strong>. O Easy deve fluir conversando; o Threshold é desconforto controlado;
        Intervalos são ~3-5min de esforço alto. Se você tá no taper, talvez ajustar de acordo com a fase.
      </div>
    </>
  );
}
