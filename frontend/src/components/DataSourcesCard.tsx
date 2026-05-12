import type { DataSource, DataSourcesStatus } from "../api/client";

const STATUS_COLOR: Record<string, string> = {
  fresh: "var(--good, #4ade80)",
  ok: "var(--accent, #60a5fa)",
  stale: "var(--warn, #fbbf24)",
  old: "var(--danger, #ef4444)",
  unknown: "var(--muted)",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "2-digit" });
}

function rangeLabel(s: DataSource): string {
  if (!s.first || !s.last) return "—";
  return `${fmtDate(s.first)} → ${fmtDate(s.last)}`;
}

function daysAgoLabel(d: number | null): string {
  if (d == null) return "—";
  if (d === 0) return "hoje";
  if (d === 1) return "ontem";
  if (d < 30) return `${d} dias atrás`;
  if (d < 60) return `${Math.round(d / 7)} sem atrás`;
  if (d < 365) return `${Math.round(d / 30)} meses atrás`;
  return `${(d / 365).toFixed(1)} anos atrás`;
}

export function DataSourcesCard({ data }: { data: DataSourcesStatus }) {
  if (!data.available || !data.sources.length) {
    return (
      <>
        <h2>Status das fontes de dados</h2>
        <div className="empty">Nenhuma fonte com dados importados ainda.</div>
      </>
    );
  }

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h2 style={{ margin: 0 }}>Status das fontes de dados</h2>
        {data.needs_attention && (
          <span className="ds-needs-attention">⚠ alguma fonte precisa atualizar</span>
        )}
      </div>
      <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
        Cobertura total: {fmtDate(data.coverage.first)} → {fmtDate(data.coverage.last)} · hoje {fmtDate(data.today)}
      </div>

      <div className="ds-list" style={{ marginTop: 12 }}>
        {data.sources.map((s) => (
          <div key={s.kind} className={`ds-row ds-row-${s.status}`}>
            <div className="ds-row-head">
              <span className="ds-icon">{s.icon}</span>
              <span className="ds-label">{s.label}</span>
              <span
                className="ds-status"
                style={{ color: STATUS_COLOR[s.status] }}
                title={`${s.days_since} dias desde a última atualização`}
              >
                {s.status_label}
              </span>
            </div>
            <div className="ds-row-meta">
              <span className="muted">{rangeLabel(s)}</span>
              <span className="muted">·</span>
              <span className="muted">{s.count.toLocaleString("pt-BR")} registros</span>
              <span className="muted">·</span>
              <span className="muted">última: {daysAgoLabel(s.days_since)}</span>
            </div>
            {s.suggestion && (
              <div className="ds-suggestion">
                💡 <code>{s.suggestion}</code>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="ds-legend">
        <span><span className="ds-dot" style={{ background: STATUS_COLOR.fresh }} /> &lt; 7 dias</span>
        <span><span className="ds-dot" style={{ background: STATUS_COLOR.ok }} /> &lt; 30 dias</span>
        <span><span className="ds-dot" style={{ background: STATUS_COLOR.stale }} /> &lt; 90 dias</span>
        <span><span className="ds-dot" style={{ background: STATUS_COLOR.old }} /> &gt; 90 dias</span>
      </div>
    </>
  );
}
