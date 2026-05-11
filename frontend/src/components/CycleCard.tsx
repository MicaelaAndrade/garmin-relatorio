import { useEffect, useState } from "react";
import { fetchCycle, type CycleDashboard } from "../api/client";

const STORAGE_KEY = "cycle_card_visible";

const PHASE_COLORS = {
  menstrual: "#ef4444",
  folicular: "#4ade80",
  ovulatoria: "#fbbf24",
  lutea: "#60a5fa",
} as const;

export function CycleCard() {
  const [visible, setVisible] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === "true"; }
    catch { return false; }
  });
  const [data, setData] = useState<CycleDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!visible || data) return;
    fetchCycle().then(setData).catch((e) => setError(String(e)));
  }, [visible, data]);

  const toggle = () => {
    const next = !visible;
    setVisible(next);
    try { localStorage.setItem(STORAGE_KEY, String(next)); } catch { /* noop */ }
  };

  if (!visible) {
    return (
      <>
        <h2>Ciclo menstrual</h2>
        <div className="label" style={{ marginBottom: 12 }}>
          Conteúdo oculto. Tudo armazenado localmente, nada sai do seu computador.
        </div>
        <button onClick={toggle} className="btn">Mostrar</button>
      </>
    );
  }

  if (error) return <><h2>Ciclo menstrual</h2><div className="empty">Erro: {error}</div></>;
  if (!data) return <><h2>Ciclo menstrual</h2><div className="empty">Carregando…</div></>;

  const { current, history } = data;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Ciclo menstrual</h2>
        <button onClick={toggle} className="btn-link">Ocultar</button>
      </div>

      {!current.available && (
        <div className="empty">{current.reason || "Sem dados"}</div>
      )}

      {current.available && current.phase && (
        <>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginTop: 8 }}>
            <span className="big">D{current.cycle_day}</span>
            <span
              className="zone"
              style={{ background: `${PHASE_COLORS[current.phase]}33`, color: PHASE_COLORS[current.phase] }}
            >
              {current.phase_label}
            </span>
            {current.estimated_cycle && (
              <span className="label">(estimado — Garmin sem log recente)</span>
            )}
          </div>
          <div className="label" style={{ marginTop: 4 }}>
            Próxima menstruação ~{current.next_period_estimated} ·
            ciclo médio {current.avg_cycle_length}d
          </div>
          <p className="recommendation" style={{ marginTop: 12 }}>
            <strong>Treino:</strong> {current.training_advice}
          </p>
          <p className="recommendation" style={{ marginTop: 4 }}>
            <strong>Intensidade:</strong> {current.intensity_advice}
          </p>
        </>
      )}

      {history.available && (
        <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
          <div className="label" style={{ marginBottom: 6 }}>Histórico ({history.count} ciclos)</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 13 }}>
            <div><span className="muted">Média:</span> {history.avg_length}d</div>
            <div><span className="muted">Variação:</span> {history.variation_days}d</div>
            <div><span className="muted">Min:</span> {history.min_length}d</div>
            <div><span className="muted">Max:</span> {history.max_length}d</div>
          </div>
          <div className="label" style={{ marginTop: 6 }}>
            Regularidade: <strong style={{ color: "var(--text)" }}>{history.regularity}</strong>
          </div>
        </div>
      )}
    </>
  );
}
