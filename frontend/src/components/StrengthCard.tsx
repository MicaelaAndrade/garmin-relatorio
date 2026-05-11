import { useEffect, useState } from "react";
import {
  fetchStrengthRoutine,
  type StrengthDashboard,
  type StrengthExercise,
  type StrengthRoutine,
  type StrengthRoutineSummary,
} from "../api/client";

function ExerciseRow({ ex }: { ex: StrengthExercise }) {
  const [open, setOpen] = useState(false);
  const hasDetail = !!ex.instructions;
  const loadLabel =
    ex.load_kg != null
      ? `${ex.load_kg}kg`
      : ex.load_text && ex.load_text.toLowerCase().includes("nenhum")
      ? "—"
      : ex.load_text || "—";

  return (
    <div className={`str-row${ex.is_warmup ? " str-warmup" : ""}`}>
      <div
        className="str-row-head"
        onClick={hasDetail ? () => setOpen((v) => !v) : undefined}
        title={hasDetail ? "Clique pra ver instruções" : ex.name}
      >
        <span className="str-order">{ex.order_idx}</span>
        <span className="str-name">{ex.name}</span>
        <span className="str-sets">{ex.sets || "—"}</span>
        <span className={`str-load${ex.load_kg ? " str-load-num" : ""}`}>{loadLabel}</span>
        <span className="str-rest">{ex.rest_text || "—"}</span>
        {hasDetail && <span className="str-toggle">{open ? "▲" : "▼"}</span>}
      </div>
      {open && ex.instructions && (
        <div className="str-instructions">{ex.instructions}</div>
      )}
    </div>
  );
}

function RoutineDetail({ routine }: { routine: StrengthRoutine }) {
  const totalLoad = routine.exercises.reduce(
    (s, e) => s + (e.load_kg || 0) * _parseSetsCount(e.sets),
    0,
  );
  const warmupCount = routine.exercises.filter((e) => e.is_warmup).length;
  const mainCount = routine.exercises.length - warmupCount;
  return (
    <>
      <div className="str-totals">
        <span>
          <strong>{mainCount}</strong> exercícios + <strong>{warmupCount}</strong> alongamentos
        </span>
        {totalLoad > 0 && (
          <span>
            Volume total ≈ <strong>{Math.round(totalLoad)}kg</strong>
          </span>
        )}
      </div>
      <div className="str-table">
        <div className="str-row str-header">
          <span className="str-order">#</span>
          <span className="str-name">Exercício</span>
          <span className="str-sets">Séries</span>
          <span className="str-load">Carga</span>
          <span className="str-rest">Rest</span>
        </div>
        {routine.exercises.map((ex) => (
          <ExerciseRow key={ex.id} ex={ex} />
        ))}
      </div>
    </>
  );
}

function _parseSetsCount(sets: string | null): number {
  if (!sets) return 0;
  // pega o ultimo grupo NxM e devolve N*M (estimativa de reps total)
  const matches = [...sets.matchAll(/(\d+)\s*[xX]\s*(\d+)/g)];
  if (!matches.length) return 0;
  const last = matches[matches.length - 1];
  return parseInt(last[1], 10) * parseInt(last[2], 10);
}

export function StrengthCard({ data }: { data: StrengthDashboard }) {
  const [selectedId, setSelectedId] = useState<number | null>(
    data.today?.id ?? data.routines[0]?.id ?? null,
  );
  const [routine, setRoutine] = useState<StrengthRoutine | null>(data.today);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selectedId == null) return;
    if (data.today && selectedId === data.today.id) {
      setRoutine(data.today);
      return;
    }
    setLoading(true);
    fetchStrengthRoutine(selectedId)
      .then((r) => setRoutine(r))
      .catch(() => setRoutine(null))
      .finally(() => setLoading(false));
  }, [selectedId, data.today]);

  if (!data.available) {
    return (
      <>
        <h2>Fortalecimento (MFit)</h2>
        <div className="empty">
          Nenhuma rotina importada ainda.
          <div className="label" style={{ marginTop: 8 }}>
            Importe com: <code>uv run garmin-relatorio import-mfit &lt;url-ou-path-do-pdf&gt;</code>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="str-head">
        <div>
          <h2 style={{ display: "inline" }}>Fortalecimento</h2>
          <span className="muted" style={{ marginLeft: 8, fontSize: 11 }}>via MFit Personal</span>
        </div>
        {data.today && (
          <span className="str-today-tag">HOJE · {data.today_weekday_label.toUpperCase()}</span>
        )}
      </div>

      {data.routines.length > 1 && (
        <div className="str-tabs">
          {data.routines.map((r: StrengthRoutineSummary) => (
            <button
              key={r.id}
              className={`str-tab${r.id === selectedId ? " str-tab-active" : ""}`}
              onClick={() => setSelectedId(r.id)}
            >
              {r.name}
              {r.weekday_label && (
                <span className="muted" style={{ marginLeft: 6, fontSize: 10 }}>
                  {r.weekday_label}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {loading && <div className="empty">Carregando…</div>}
      {!loading && routine && <RoutineDetail routine={routine} />}
      {!loading && !routine && (
        <div className="empty">Selecione uma rotina.</div>
      )}
    </>
  );
}
