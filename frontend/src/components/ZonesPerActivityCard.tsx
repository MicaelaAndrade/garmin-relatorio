import { useMemo, useState } from "react";
import type { RecentActivity, Sport } from "../api/client";
import { formatTime } from "../api/client";

const ZONE_COLORS: Record<string, string> = {
  z0: "#3f4856",
  z1: "#60a5fa",
  z2: "#4ade80",
  z3: "#fbbf24",
  z4: "#fb923c",
  z5: "#ef4444",
};

const SPORT_ICON: Record<Sport, string> = {
  run: "🏃",
  bike: "🚴",
  swim: "🏊",
  yoga: "🧘",
  strength: "💪",
  walking: "🚶",
  other: "•",
};

const SPORT_LABEL = { all: "Todos", run: "Corrida", bike: "Bike", swim: "Nado" } as const;

type FilterSport = "all" | "run" | "bike" | "swim";

function totalZoneSeconds(zones: Record<string, number> | undefined): number {
  if (!zones) return 0;
  return Object.values(zones).reduce((s, v) => s + v, 0);
}

function dominantZone(zones: Record<string, number> | undefined): string | null {
  if (!zones) return null;
  let best: [string, number] | null = null;
  for (const [k, v] of Object.entries(zones)) {
    if (k === "z0") continue; // ignora "abaixo de Z1"
    if (!best || v > best[1]) best = [k, v];
  }
  return best ? best[0].toUpperCase() : null;
}

function formatShortDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function ZoneBar({ zones }: { zones: Record<string, number> }) {
  const total = totalZoneSeconds(zones);
  if (total === 0) return <div className="zpa-bar zpa-bar-empty">—</div>;
  return (
    <div className="zpa-bar" title="Tempo em cada zona FC">
      {(["z0", "z1", "z2", "z3", "z4", "z5"] as const).map((z) => {
        const v = zones[z] || 0;
        if (v === 0) return null;
        const pct = (v / total) * 100;
        const min = Math.round(v / 60);
        return (
          <span
            key={z}
            className="zpa-seg"
            style={{ flex: pct, background: ZONE_COLORS[z] }}
            title={`${z.toUpperCase()}: ${min} min (${pct.toFixed(0)}%)`}
          />
        );
      })}
    </div>
  );
}

export function ZonesPerActivityCard({ data }: { data: RecentActivity[] }) {
  const [filter, setFilter] = useState<FilterSport>("all");

  const filtered = useMemo(() => {
    return data
      .filter((a) => a.zones_s && totalZoneSeconds(a.zones_s) > 60)
      .filter((a) =>
        filter === "all"
          ? a.sport === "run" || a.sport === "bike" || a.sport === "swim"
          : a.sport === filter,
      )
      .slice(0, 15);
  }, [data, filter]);

  return (
    <>
      <div className="zpa-head">
        <div>
          <h2 style={{ display: "inline" }}>Zonas Z1-Z5 por treino</h2>
          <span className="muted" style={{ marginLeft: 8, fontSize: 11 }}>
            últimas {filtered.length} sessões com FC
          </span>
        </div>
        <div className="zpa-tabs">
          {(Object.keys(SPORT_LABEL) as FilterSport[]).map((s) => (
            <button
              key={s}
              type="button"
              className={`zpa-tab${filter === s ? " zpa-tab-active" : ""}`}
              onClick={() => setFilter(s)}
            >
              {SPORT_LABEL[s]}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="empty">
          Nenhum treino com dados de zona FC no filtro escolhido.
        </div>
      ) : (
        <div className="zpa-list">
          <div className="zpa-row zpa-header">
            <span></span>
            <span>Dia</span>
            <span>Treino</span>
            <span>Tempo</span>
            <span>Distribuição Z1 → Z5</span>
            <span>Zona dom.</span>
          </div>
          {filtered.map((a) => {
            const dom = dominantZone(a.zones_s);
            const domColor = dom ? ZONE_COLORS[dom.toLowerCase()] : "var(--muted)";
            return (
              <div key={a.id} className="zpa-row">
                <span style={{ fontSize: 16 }}>{SPORT_ICON[a.sport] || "•"}</span>
                <span className="muted">{formatShortDate(a.started_at)}</span>
                <span className="zpa-name" title={a.name || a.sport}>
                  {a.name || a.sport}
                </span>
                <span className="zpa-time">{formatTime(a.duration_s)}</span>
                <ZoneBar zones={a.zones_s!} />
                <span className="zpa-dom" style={{ color: domColor }}>
                  {dom || "—"}
                </span>
              </div>
            );
          })}
          <div className="zpa-legend">
            <span><span className="zpa-dot" style={{ background: ZONE_COLORS.z1 }} /> Z1 recuperação</span>
            <span><span className="zpa-dot" style={{ background: ZONE_COLORS.z2 }} /> Z2 base aeróbica</span>
            <span><span className="zpa-dot" style={{ background: ZONE_COLORS.z3 }} /> Z3 limiar</span>
            <span><span className="zpa-dot" style={{ background: ZONE_COLORS.z4 }} /> Z4 anaeróbio</span>
            <span><span className="zpa-dot" style={{ background: ZONE_COLORS.z5 }} /> Z5 VO2max</span>
          </div>
        </div>
      )}
    </>
  );
}
