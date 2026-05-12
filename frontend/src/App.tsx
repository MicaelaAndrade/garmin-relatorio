import { useEffect, useState } from "react";
import { CalendarHeatmap } from "./components/CalendarHeatmap";
import { Card, type DashTab } from "./components/Card";
import { CaloriesCard } from "./components/CaloriesCard";
import { CoachScheduleCard } from "./components/CoachScheduleCard";
import { CurrentWeekCard } from "./components/CurrentWeekCard";
import { CycleCard } from "./components/CycleCard";
import { CyclePerformanceCard } from "./components/CyclePerformanceCard";
import { GarminPredictionsCard } from "./components/GarminPredictionsCard";
import { InjuryRiskCard } from "./components/InjuryRiskCard";
import { OvertrainingCard } from "./components/OvertrainingCard";
import { PaceEvolutionCard } from "./components/PaceEvolutionCard";
import { PerformanceCard } from "./components/PerformanceCard";
import { PerformanceMgmtCard } from "./components/PerformanceMgmtCard";
import { PersonalRecordsCard } from "./components/PersonalRecordsCard";
import { ProfileCard } from "./components/ProfileCard";
import { RaceComparisonCard } from "./components/RaceComparisonCard";
import { RaceDayCard } from "./components/RaceDayCard";
import { RacesCard } from "./components/RacesCard";
import { RecentActivitiesTable } from "./components/RecentActivitiesTable";
import { SleepCard } from "./components/SleepCard";
import { SleepDetailCard } from "./components/SleepDetailCard";
import { StrengthCard } from "./components/StrengthCard";
import { TemperatureTrendCard } from "./components/TemperatureTrendCard";
import { TrainingPlanCard } from "./components/TrainingPlanCard";
import { VdotCard } from "./components/VdotCard";
import { Vo2maxCard } from "./components/Vo2maxCard";
import { WellnessCard } from "./components/WellnessCard";
import { YearOverYearCard } from "./components/YearOverYearCard";
import { VolumeChart } from "./components/VolumeChart";
import { WeeklySummaryCard } from "./components/WeeklySummaryCard";
import { ZonesCard } from "./components/ZonesCard";
import { ZonesPerActivityCard } from "./components/ZonesPerActivityCard";
import { MetricsTutorialPage } from "./components/MetricsTutorialPage";
import { WrappedPage } from "./components/WrappedPage";
import { fetchDashboard, triggerRefresh, type Dashboard } from "./api/client";

export default function App() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showWrapped, setShowWrapped] = useState(false);
  const [showTutorial, setShowTutorial] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const [tab, setTab] = useState<DashTab>(() => {
    try { return (localStorage.getItem("dash_tab") as DashTab) || "today"; } catch { return "today"; }
  });

  useEffect(() => {
    try { localStorage.setItem("dash_tab", tab); } catch { /* noop */ }
  }, [tab]);
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    try {
      return (localStorage.getItem("theme") as "dark" | "light") || "dark";
    } catch {
      return "dark";
    }
  });

  useEffect(() => {
    document.body.classList.toggle("theme-light", theme === "light");
    try { localStorage.setItem("theme", theme); } catch { /* noop */ }
  }, [theme]);

  useEffect(() => {
    fetchDashboard().then(setData).catch((e) => setError(String(e)));
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshMessage(null);
    try {
      const result = await triggerRefresh();
      const total = Object.entries(result.results).reduce((sum, [, v]) => {
        const r = v as { inserted?: number; updated?: number; error?: string };
        if (r.error) return sum;
        return sum + (r.inserted || 0) + (r.updated || 0);
      }, 0);
      const errors = Object.entries(result.results).filter(([, v]) => (v as { error?: string }).error);
      setRefreshMessage(
        errors.length
          ? `Atualizou em ${result.elapsed_s}s · ${total} novos · ${errors.length} fonte(s) com erro`
          : `Atualizado em ${result.elapsed_s}s · ${total} novos registros`,
      );
      const fresh = await fetchDashboard();
      setData(fresh);
    } catch (e) {
      setRefreshMessage(`Erro: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setRefreshing(false);
      setTimeout(() => setRefreshMessage(null), 5000);
    }
  };

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
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {refreshMessage && (
            <span className="muted" style={{ fontSize: 11 }}>{refreshMessage}</span>
          )}
          <button
            className="btn"
            onClick={handleRefresh}
            disabled={refreshing}
            title="Puxa atividades novas do Garmin agora"
          >
            {refreshing ? "⏳ Atualizando…" : "↻ Atualizar"}
          </button>
          <button
            className="btn"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            title="Alternar tema"
          >
            {theme === "dark" ? "☀️ Light" : "🌙 Dark"}
          </button>
          <button className="btn" onClick={() => setShowTutorial(true)} title="O que cada métrica significa">
            ❓ Métricas
          </button>
          <button className="btn btn-primary" onClick={() => setShowWrapped(true)} title="Ver stats anuais">
            ✨ Wrapped {new Date().getFullYear()}
          </button>
        </div>
      </header>
      {showWrapped && <WrappedPage onClose={() => setShowWrapped(false)} />}
      {showTutorial && <MetricsTutorialPage data={data} onClose={() => setShowTutorial(false)} />}

      <div className="dash-tabs">
        <button
          className={`dash-tab${tab === "today" ? " dash-tab-active" : ""}`}
          onClick={() => setTab("today")}
        >
          📍 Hoje
        </button>
        <button
          className={`dash-tab${tab === "analysis" ? " dash-tab-active" : ""}`}
          onClick={() => setTab("analysis")}
        >
          📊 Análise
        </button>
        <button
          className={`dash-tab${tab === "all" ? " dash-tab-active" : ""}`}
          onClick={() => setTab("all")}
        >
          🔬 Tudo
        </button>
      </div>

      <div className="grid">
        {tab !== "all" && (
          <div className="section-title">
            {tab === "today" ? "📍 Hoje — o essencial" : "📊 Análise — tendências"}
          </div>
        )}

        {tab === "all" && <div className="section-title">Perfil</div>}
        <Card storageKey="profile" className="col-6" tabs={["today", "analysis"]} currentTab={tab}>
          <ProfileCard data={data.profile} />
        </Card>
        <Card storageKey="calories" className="col-6" tabs={["today", "analysis"]} currentTab={tab}>
          <CaloriesCard data={data.calories} />
        </Card>

        {tab === "all" && <div className="section-title">Resumo de hoje</div>}
        <Card storageKey="current-week" className="col-3" tabs={["today", "analysis"]} currentTab={tab}>
          <CurrentWeekCard data={data.current_week} />
        </Card>
        <Card storageKey="injury-risk" className="col-3" tabs={["today", "analysis"]} currentTab={tab}>
          <InjuryRiskCard current={data.injury_risk} series={data.acwr_series} />
        </Card>
        <Card storageKey="overtraining" className="col-3" tabs={["today", "analysis"]} currentTab={tab}>
          <OvertrainingCard data={data.overtraining} />
        </Card>
        <Card storageKey="sleep" className="col-3" tabs={["today", "analysis"]} currentTab={tab}>
          <SleepCard sleep={data.sleep} readiness={data.readiness} />
        </Card>

        {tab === "today" && (
          <Card storageKey="coach-today" className="col-12" tabs={["today"]} currentTab={tab}>
            <CoachScheduleCard schedule={data.coach_schedule} today={data.coach_today} />
          </Card>
        )}
        {tab === "today" && (
          <Card storageKey="recent-today" className="col-12" tabs={["today"]} currentTab={tab}>
            <RecentActivitiesTable data={data.recent_activities} />
          </Card>
        )}

        <Card storageKey="sleep-detail" className="col-12" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <SleepDetailCard data={data.sleep_detail} />
        </Card>
        <Card storageKey="wellness" className="col-12" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <WellnessCard data={data.wellness} />
        </Card>
        <Card storageKey="yoy" className="col-12" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <YearOverYearCard data={data.year_over_year} />
        </Card>
        <Card storageKey="pmc" className="col-12" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <PerformanceMgmtCard data={data.performance_mgmt} />
        </Card>
        <Card storageKey="vdot" className="col-12" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <VdotCard data={data.vdot} />
        </Card>
        <Card storageKey="temp-trend" className="col-12" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <TemperatureTrendCard data={data.temperature_trend} />
        </Card>
        {(() => {
          let cycleVisible = false;
          try { cycleVisible = localStorage.getItem("cycle_card_visible") === "true"; } catch { /* noop */ }
          return cycleVisible ? (
            <Card storageKey="cycle-perf" className="col-12" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
              <CyclePerformanceCard data={data.cycle_performance} />
            </Card>
          ) : null;
        })()}

        <Card storageKey="weekly-summary" className="col-12" tabs={["analysis"]} currentTab={tab}>
          <WeeklySummaryCard aiAvailable={data.ai_available} />
        </Card>

        {tab === "all" && <div className="section-title">Treino</div>}
        <Card storageKey="volume" className="col-8" tabs={["analysis"]} currentTab={tab}>
          <h2>Volume semanal por modalidade</h2>
          <VolumeChart data={data.weekly_volume} />
        </Card>
        <Card storageKey="vo2max" className="col-4" tabs={["analysis"]} currentTab={tab}>
          <Vo2maxCard latest={data.vo2max.latest} series={data.vo2max.series} />
        </Card>

        <Card storageKey="zones-run" className="col-4" tabs={["analysis"]} currentTab={tab}>
          <ZonesCard sport="run" weekly={data.zones_by_sport.run.weekly} pol={data.zones_by_sport.run.polarization} />
        </Card>
        <Card storageKey="zones-bike" className="col-4" tabs={["analysis"]} currentTab={tab}>
          <ZonesCard sport="bike" weekly={data.zones_by_sport.bike.weekly} pol={data.zones_by_sport.bike.polarization} />
        </Card>
        <Card storageKey="zones-swim" className="col-4" tabs={["analysis"]} currentTab={tab}>
          <ZonesCard sport="swim" weekly={data.zones_by_sport.swim.weekly} pol={data.zones_by_sport.swim.polarization} />
        </Card>
        <Card storageKey="pace-evo" className="col-12" tabs={["analysis"]} currentTab={tab}>
          <PaceEvolutionCard data={data.pace_evolution} />
        </Card>
        <Card storageKey="zones-per-activity" className="col-12" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <ZonesPerActivityCard data={data.recent_activities} />
        </Card>

        <Card storageKey="calendar" className="col-12" tabs={["analysis"]} currentTab={tab}>
          <CalendarHeatmap data={data.calendar} />
        </Card>

        {tab === "all" && <div className="section-title">Plano</div>}
        {tab !== "today" && (
          <Card storageKey="coach" className="col-12" tabs={["analysis"]} currentTab={tab}>
            <CoachScheduleCard schedule={data.coach_schedule} today={data.coach_today} />
          </Card>
        )}
        <Card storageKey="strength" className="col-12" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <StrengthCard data={data.strength} />
        </Card>
        <Card storageKey="training-plan" className="col-12" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <TrainingPlanCard plan={data.training_plan} />
        </Card>

        {tab === "all" && <div className="section-title">Provas e ciclo</div>}
        <Card storageKey="race-day" className="col-12" tabs={["today", "analysis"]} currentTab={tab}>
          <RaceDayCard />
        </Card>
        <Card storageKey="races" className="col-8" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <RacesCard />
        </Card>
        <Card storageKey="cycle" className="col-4" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <CycleCard />
        </Card>

        {tab === "all" && <div className="section-title">Performance</div>}
        <Card storageKey="garmin-pred" className="col-6" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <GarminPredictionsCard current={data.garmin_predictions} series={data.garmin_predictions_series} />
        </Card>
        <Card storageKey="race-compare" className="col-6" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <RaceComparisonCard data={data.race_comparison} />
        </Card>
        <Card storageKey="perf-riegel" className="col-6" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <PerformanceCard predictions={data.predictions} />
        </Card>
        <Card storageKey="prs" className="col-6" defaultCollapsed tabs={["analysis"]} currentTab={tab}>
          <PersonalRecordsCard data={data.personal_records} />
        </Card>

        {tab !== "today" && (
          <>
            {tab === "all" && <div className="section-title">Histórico</div>}
            <Card storageKey="recent-activities" className="col-12" tabs={["analysis"]} currentTab={tab}>
              <RecentActivitiesTable data={data.recent_activities} />
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
