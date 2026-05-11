import { useEffect, useState } from "react";
import { CalendarHeatmap } from "./components/CalendarHeatmap";
import { CaloriesCard } from "./components/CaloriesCard";
import { CoachScheduleCard } from "./components/CoachScheduleCard";
import { CurrentWeekCard } from "./components/CurrentWeekCard";
import { CycleCard } from "./components/CycleCard";
import { GarminPredictionsCard } from "./components/GarminPredictionsCard";
import { InjuryRiskCard } from "./components/InjuryRiskCard";
import { OvertrainingCard } from "./components/OvertrainingCard";
import { PaceEvolutionCard } from "./components/PaceEvolutionCard";
import { PerformanceCard } from "./components/PerformanceCard";
import { PersonalRecordsCard } from "./components/PersonalRecordsCard";
import { ProfileCard } from "./components/ProfileCard";
import { RaceComparisonCard } from "./components/RaceComparisonCard";
import { RacesCard } from "./components/RacesCard";
import { RecentActivitiesTable } from "./components/RecentActivitiesTable";
import { SleepCard } from "./components/SleepCard";
import { StrengthCard } from "./components/StrengthCard";
import { TrainingPlanCard } from "./components/TrainingPlanCard";
import { Vo2maxCard } from "./components/Vo2maxCard";
import { VolumeChart } from "./components/VolumeChart";
import { WeeklySummaryCard } from "./components/WeeklySummaryCard";
import { ZonesCard } from "./components/ZonesCard";
import { ZonesPerActivityCard } from "./components/ZonesPerActivityCard";
import { fetchDashboard, type Dashboard } from "./api/client";

export default function App() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="container">
        <header className="top">
          <h1>Garmin Relatório</h1>
        </header>
        <div className="card">
          <h2>Erro ao carregar</h2>
          <p>{error}</p>
          <p className="label">
            Backend está rodando? <code>uv run garmin-relatorio serve --reload</code>
          </p>
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="container"><div className="empty">Carregando…</div></div>;
  }

  const today = new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div className="container">
      <header className="top">
        <div>
          <h1>Garmin Relatório</h1>
          <div className="sub">Triathlon · {today}</div>
        </div>
      </header>

      <div className="grid">
        <div className="section-title">Perfil</div>
        <div className="card col-6"><ProfileCard data={data.profile} /></div>
        <div className="card col-6"><CaloriesCard data={data.calories} /></div>

        <div className="section-title">Resumo de hoje</div>
        <div className="card col-3"><CurrentWeekCard data={data.current_week} /></div>
        <div className="card col-3"><InjuryRiskCard current={data.injury_risk} series={data.acwr_series} /></div>
        <div className="card col-3"><OvertrainingCard data={data.overtraining} /></div>
        <div className="card col-3"><SleepCard sleep={data.sleep} readiness={data.readiness} /></div>

        <div className="card col-12">
          <WeeklySummaryCard aiAvailable={data.ai_available} />
        </div>

        <div className="section-title">Treino</div>
        <div className="card col-8">
          <h2>Volume semanal por modalidade</h2>
          <VolumeChart data={data.weekly_volume} />
        </div>
        <div className="card col-4"><Vo2maxCard latest={data.vo2max.latest} series={data.vo2max.series} /></div>

        <div className="card col-4">
          <ZonesCard
            sport="run"
            weekly={data.zones_by_sport.run.weekly}
            pol={data.zones_by_sport.run.polarization}
          />
        </div>
        <div className="card col-4">
          <ZonesCard
            sport="bike"
            weekly={data.zones_by_sport.bike.weekly}
            pol={data.zones_by_sport.bike.polarization}
          />
        </div>
        <div className="card col-4">
          <ZonesCard
            sport="swim"
            weekly={data.zones_by_sport.swim.weekly}
            pol={data.zones_by_sport.swim.polarization}
          />
        </div>
        <div className="card col-12"><PaceEvolutionCard data={data.pace_evolution} /></div>
        <div className="card col-12"><ZonesPerActivityCard data={data.recent_activities} /></div>

        <div className="card col-12">
          <CalendarHeatmap data={data.calendar} />
        </div>

        <div className="section-title">Plano</div>
        <div className="card col-12">
          <CoachScheduleCard schedule={data.coach_schedule} today={data.coach_today} />
        </div>
        <div className="card col-12"><StrengthCard data={data.strength} /></div>
        <div className="card col-12"><TrainingPlanCard plan={data.training_plan} /></div>

        <div className="section-title">Provas e ciclo</div>
        <div className="card col-8"><RacesCard /></div>
        <div className="card col-4"><CycleCard /></div>

        <div className="section-title">Performance</div>
        <div className="card col-6">
          <GarminPredictionsCard current={data.garmin_predictions} series={data.garmin_predictions_series} />
        </div>
        <div className="card col-6"><RaceComparisonCard data={data.race_comparison} /></div>

        <div className="card col-6"><PerformanceCard predictions={data.predictions} /></div>
        <div className="card col-6"><PersonalRecordsCard data={data.personal_records} /></div>

        <div className="section-title">Histórico</div>
        <div className="card col-12">
          <RecentActivitiesTable data={data.recent_activities} />
        </div>
      </div>
    </div>
  );
}
