import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ProfileDashboard } from "../api/client";

const BMI_LABEL: Record<NonNullable<ProfileDashboard["bmi_zone"]>, string> = {
  abaixo: "Abaixo do peso",
  saudavel: "Saudável",
  sobrepeso: "Sobrepeso",
  obesidade: "Obesidade",
};
const BMI_COLOR: Record<NonNullable<ProfileDashboard["bmi_zone"]>, string> = {
  abaixo: "#60a5fa",
  saudavel: "#4ade80",
  sobrepeso: "#fbbf24",
  obesidade: "#ef4444",
};

function formatMonth(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { month: "short", year: "2-digit" });
}

export function ProfileCard({ data }: { data: ProfileDashboard }) {
  if (!data.available) {
    return (
      <>
        <h2>Seu perfil</h2>
        <div className="empty">
          Sem dados de perfil. Importe com:
          <code style={{ marginLeft: 6 }}>uv run garmin-relatorio ingest-export --what profile</code>
        </div>
      </>
    );
  }

  const weightDelta = data.weight.delta_kg;
  const weightDeltaText =
    weightDelta != null
      ? `${weightDelta > 0 ? "+" : ""}${weightDelta} kg desde ${data.weight.first_date?.slice(0, 7) || "início"}`
      : null;
  const weightDeltaColor = weightDelta == null ? "var(--muted)" : weightDelta < 0 ? "var(--accent)" : "var(--info)";

  const vo2Delta = data.vo2max.delta;
  const vo2DeltaText =
    vo2Delta != null
      ? `${vo2Delta > 0 ? "+" : ""}${vo2Delta} desde ${data.vo2max.first_date?.slice(0, 7) || "início"}`
      : null;

  const weightSeries = data.weight.series.map((p) => ({
    month: formatMonth(p.date),
    kg: p.kg,
  }));

  return (
    <>
      <h2>Seu perfil</h2>
      <div className="profile-grid">
        {data.age != null && (
          <div className="profile-stat">
            <span className="profile-label">Idade</span>
            <span className="profile-value">{data.age}</span>
            <span className="profile-unit">anos</span>
          </div>
        )}
        {data.weight.kg != null && (
          <div className="profile-stat">
            <span className="profile-label">Peso</span>
            <span className="profile-value">{data.weight.kg.toFixed(1)}</span>
            <span className="profile-unit">kg</span>
            {weightDeltaText && (
              <span className="profile-delta" style={{ color: weightDeltaColor }}>
                {weightDeltaText}
              </span>
            )}
          </div>
        )}
        {data.height_cm != null && (
          <div className="profile-stat">
            <span className="profile-label">Altura</span>
            <span className="profile-value">{data.height_cm.toFixed(0)}</span>
            <span className="profile-unit">cm</span>
          </div>
        )}
        {data.bmi != null && data.bmi_zone && (
          <div className="profile-stat">
            <span className="profile-label">IMC</span>
            <span className="profile-value" style={{ color: BMI_COLOR[data.bmi_zone] }}>
              {data.bmi}
            </span>
            <span className="profile-unit" style={{ color: BMI_COLOR[data.bmi_zone] }}>
              {BMI_LABEL[data.bmi_zone]}
            </span>
          </div>
        )}
        {data.vo2max.value != null && (
          <div className="profile-stat">
            <span className="profile-label">VO2max</span>
            <span className="profile-value">{data.vo2max.value}</span>
            <span className="profile-unit">ml/kg/min</span>
            {vo2DeltaText && (
              <span
                className="profile-delta"
                style={{ color: vo2Delta && vo2Delta > 0 ? "var(--accent)" : "var(--muted)" }}
              >
                {vo2DeltaText}
              </span>
            )}
          </div>
        )}
        {data.ftp_watts != null && (
          <div className="profile-stat">
            <span className="profile-label">FTP (bike)</span>
            <span className="profile-value">{data.ftp_watts}</span>
            <span className="profile-unit">W</span>
          </div>
        )}
        {data.max_hr_override != null && (
          <div className="profile-stat">
            <span className="profile-label">FCmax (override)</span>
            <span className="profile-value">{data.max_hr_override}</span>
            <span className="profile-unit">bpm</span>
          </div>
        )}
      </div>

      {weightSeries.length >= 2 && (
        <div style={{ marginTop: 8 }}>
          <div className="label" style={{ marginBottom: 2, fontSize: 10 }}>Evolução do peso</div>
          <ResponsiveContainer width="100%" height={80}>
            <LineChart data={weightSeries} margin={{ top: 2, right: 4, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#2a3340" strokeDasharray="3 3" />
              <XAxis dataKey="month" stroke="#8b96a8" fontSize={9} />
              <YAxis
                stroke="#8b96a8"
                fontSize={9}
                unit="kg"
                domain={["dataMin - 1", "dataMax + 1"]}
                width={30}
              />
              <Tooltip
                contentStyle={{ background: "#1a2028", border: "1px solid #2a3340", borderRadius: 8 }}
                formatter={(v: number) => [`${v} kg`, "Peso"]}
              />
              <Line type="monotone" dataKey="kg" stroke="#60a5fa" strokeWidth={2} dot={{ r: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </>
  );
}
