import { useState } from "react";
import { fetchWeeklySummary, type WeeklySummary } from "../api/client";

export function WeeklySummaryCard({ aiAvailable }: { aiAvailable: boolean }) {
  const [summary, setSummary] = useState<WeeklySummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async (useAi: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWeeklySummary(useAi);
      setSummary(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <h2>Resumo da semana</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button
          onClick={() => generate(true)}
          disabled={loading || !aiAvailable}
          className="btn btn-primary"
          title={aiAvailable ? "Usa Claude Haiku 4.5" : "Configure ANTHROPIC_API_KEY no .env"}
        >
          {loading ? "Gerando…" : "Gerar com IA"}
        </button>
        <button onClick={() => generate(false)} disabled={loading} className="btn">
          {loading ? "Gerando…" : "Gerar (template)"}
        </button>
      </div>
      {!aiAvailable && (
        <div className="label" style={{ marginBottom: 8 }}>
          IA nao disponivel — adicione <code>ANTHROPIC_API_KEY</code> no <code>.env</code> pra habilitar
        </div>
      )}
      {error && <div className="empty" style={{ padding: 12 }}>Erro: {error}</div>}
      {summary && (
        <div>
          <div className="label" style={{ marginBottom: 8 }}>
            {summary.week_start} a {summary.week_end} · gerado por <code>{summary.method}</code>
            {summary.error && <span style={{ color: "var(--warn)" }}> · IA falhou, fallback usado</span>}
          </div>
          <p style={{ lineHeight: 1.6, margin: 0 }}>{summary.text}</p>
        </div>
      )}
      {!summary && !error && !loading && (
        <div className="label">Clique acima pra gerar resumo semanal.</div>
      )}
    </>
  );
}
