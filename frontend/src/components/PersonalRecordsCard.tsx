import type { PersonalRecord } from "../api/client";
import { formatTime } from "../api/client";

/**
 * Garmin grava o "value" do PR de jeito diferente conforme o tipo:
 * - "Best NK Run" / "Best NK Pool Swim" → tempo em segundos
 * - "Longest Run/Ride/Swim" → distância em metros
 * - "Most Steps in a Day/Week" → contagem de passos
 * - "Best Pace ..." → pace em sec/km
 */
function formatPrValue(record: PersonalRecord): string {
  const t = record.record_type.toLowerCase();
  if (t.includes("best") && (t.includes("run") || t.includes("swim") || t.includes("marathon"))) {
    return formatTime(Math.round(record.value));
  }
  if (t.includes("longest")) {
    const km = record.value / 1000;
    return km >= 1 ? `${km.toFixed(2)} km` : `${record.value.toFixed(0)} m`;
  }
  if (t.includes("steps")) {
    return record.value.toLocaleString("pt-BR");
  }
  if (t.includes("pace")) {
    const m = Math.floor(record.value / 60);
    const s = Math.round(record.value % 60);
    return `${m}:${String(s).padStart(2, "0")}/km`;
  }
  return record.value.toFixed(0);
}

function formatDate(s: string): string {
  // "Wed May 06 21:32:00 GMT 2026" ou "2026-05-06"
  const d = new Date(s);
  if (isNaN(d.getTime())) return s.slice(0, 10);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "2-digit" });
}

export function PersonalRecordsCard({ data }: { data: PersonalRecord[] }) {
  if (data.length === 0) {
    return (
      <>
        <h2>Personal records</h2>
        <div className="empty">Sem PRs registrados.</div>
      </>
    );
  }
  return (
    <>
      <h2>Personal records ({data.length})</h2>
      <div className="prs">
        {data.map((pr) => (
          <div key={pr.pr_id} className="pr-row">
            <span className="pr-type">{pr.record_type}</span>
            <span className="pr-value">{formatPrValue(pr)}</span>
            <span className="pr-date">{formatDate(pr.achieved_at)}</span>
          </div>
        ))}
      </div>
    </>
  );
}
