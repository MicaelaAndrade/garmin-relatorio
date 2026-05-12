export type Sport = "run" | "bike" | "swim" | "yoga" | "strength" | "walking" | "other";
export type Zone = "destreino" | "otimo" | "moderado" | "alto" | "indefinido" | "sem_dados";

export interface CurrentWeek {
  week_start: string;
  sessions: number;
  duration_min: number;
  distance_km: number;
  by_sport: Record<string, { sessions: number; duration_min: number; distance_km: number }>;
}

export interface WeeklyVolume {
  week_start: string;
  sport: Sport;
  sessions: number;
  duration_min: number;
  distance_km: number;
  avg_hr: number | null;
}

export interface AcwrPoint {
  day: string;
  load: number;
  acute_7d: number | null;
  chronic_28d: number | null;
  acwr: number | null;
  zone: Zone;
}

export interface InjuryRisk extends AcwrPoint {
  recommendation: string;
}

export interface Readiness {
  flag: "verde" | "amarelo" | "vermelho" | "sem_dados";
  notes: string[];
}

export interface SleepNight {
  date: string;
  total_min: number | null;
  deep_min: number | null;
  rem_min: number | null;
  score: number | null;
  total_h: number | null;
}

export interface DailyMetric {
  date: string;
  resting_hr: number | null;
  hrv_overnight: number | null;
  body_battery: number | null;
  stress_avg: number | null;
  steps: number | null;
}

export interface Prediction {
  distance_m: number;
  predicted_time_s: number;
  predicted_pace_s_km: number;
  confidence: "alta" | "media" | "baixa";
}

export interface PerformancePrediction {
  sport: Sport;
  reference: { started_at: string; distance_m: number; duration_s: number; pace_s_km: number } | null;
  predictions: Prediction[];
}

export interface GarminPrediction {
  label: string;
  distance_m: number;
  predicted_time_s: number;
  predicted_pace_s_km: number;
}

export interface GarminPredictions {
  date: string | null;
  predictions: GarminPrediction[];
}

export interface GarminPredictionPoint {
  date: string;
  race_5k_s: number | null;
  race_10k_s: number | null;
  race_half_s: number | null;
  race_marathon_s: number | null;
}

export interface Vo2maxPoint { date: string; value: number }

export interface Vo2maxLatest {
  by_sport: Record<string, { date: string; value: number }>;
}

export interface RecentActivity {
  id: number;
  source: string;
  external_id: string;
  sport: Sport;
  started_at: string;
  duration_s: number;
  distance_m: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  avg_pace_s_km: number | null;
  elevation_gain: number | null;
  calories: number | null;
  name: string | null;
  zones_s?: Record<string, number>;
}

export interface CalendarDay {
  day: string;
  sessions: number;
  duration_min: number;
  load: number;
  sports: string;
}

export interface OvertrainingSignal { kind: string; msg: string; weight: number }
export interface OvertrainingStatus {
  score: number;
  max_score: number;
  flag: "ok" | "atencao" | "alerta" | "vermelho";
  message: string;
  signals: OvertrainingSignal[];
  hrv: { last_3_avg: number; baseline_avg: number; baseline_lower: number; baseline_upper: number } | null;
  rhr: { last_3_avg: number; baseline_avg: number } | null;
  sleep: { short_nights_count: number; low_score_count: number; avg_total_min: number | null; avg_score: number | null } | null;
}

export interface PersonalRecord {
  pr_id: number;
  record_type: string;
  value: number;
  achieved_at: string;
  is_current: number;
}

export interface RaceComparisonRow {
  label: string;
  distance_m: number;
  riegel_s: number | null;
  riegel_pace: number | null;
  riegel_confidence: string | null;
  garmin_s: number | null;
  garmin_pace: number | null;
  diff_s: number | null;
}

export interface RaceComparison {
  riegel_reference: { started_at: string; distance_m: number; duration_s: number; pace_s_km: number } | null;
  garmin_date: string | null;
  rows: RaceComparisonRow[];
}

export interface Dashboard {
  current_week: CurrentWeek;
  weekly_volume: WeeklyVolume[];
  injury_risk: InjuryRisk;
  acwr_series: AcwrPoint[];
  readiness: Readiness;
  sleep: SleepNight[];
  daily_metrics: DailyMetric[];
  predictions: { run: PerformancePrediction; swim: PerformancePrediction; bike: PerformancePrediction };
  garmin_predictions: GarminPredictions;
  garmin_predictions_series: GarminPredictionPoint[];
  vo2max: { latest: Vo2maxLatest; series: Vo2maxPoint[] };
  recent_activities: RecentActivity[];
  calendar: CalendarDay[];
  overtraining: OvertrainingStatus;
  personal_records: PersonalRecord[];
  race_comparison: RaceComparison;
  zones_weekly: ZoneWeek[];
  polarization: Polarization;
  zones_by_sport: Record<"run" | "bike" | "swim", { weekly: ZoneWeek[]; polarization: Polarization }>;
  pace_evolution: PaceEvolution;
  training_plan: TrainingPlan;
  coach_schedule: CoachSchedule;
  coach_today: CoachToday;
  strength: StrengthDashboard;
  profile: ProfileDashboard;
  calories: CaloriesDashboard;
  sleep_detail: SleepDetailDashboard;
  wellness: WellnessDashboard;
  year_over_year: YearOverYear;
  performance_mgmt: PMCDashboard;
  cycle_performance: CyclePerformanceDashboard;
  vdot: VdotDashboard;
  temperature_trend: TemperatureTrend;
  ai_available: boolean;
}

export async function fetchStrengthRoutine(routineId: number): Promise<StrengthRoutine> {
  const r = await fetch(`/api/strength/${routineId}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export interface ZoneWeek {
  week_start: string;
  z0_min: number; z1_min: number; z2_min: number;
  z3_min: number; z4_min: number; z5_min: number;
  total_min: number;
}

export interface Polarization {
  days: number;
  total_min: number;
  low_pct: number | null;
  mid_pct: number | null;
  high_pct: number | null;
  verdict: "polarizado" | "limiar" | "base" | "misto" | "sem_dados";
  message: string;
}

export interface PaceMonth {
  month: string;
  sessions: number;
  total_km: number;
  avg_hr: number | null;
  avg_cadence: number | null;
  avg_pace_s_km?: number;
  avg_speed_kmh?: number;
}

export interface PaceEvolution {
  run: PaceMonth[];
  swim: PaceMonth[];
  bike: PaceMonth[];
}

export interface WeeklySummary {
  week_start: string;
  week_end: string;
  method: string;
  text: string;
  error: string | null;
}

export interface WrappedSportStat {
  sport: string;
  label: string;
  sessions: number;
  total_km: number;
  total_hours: number;
  total_kcal: number;
  pct_of_sessions: number;
}

export interface WrappedMonth {
  month: number;
  label: string;
  sessions: number;
  total_km: number;
  total_hours: number;
}

export interface WrappedDashboard {
  available: boolean;
  year: number;
  totals?: {
    sessions: number;
    km: number;
    hours: number;
    kcal_activities: number;
    kcal_total_day: number;
    elevation_m: number;
    steps: number;
    active_days: number;
    rest_days: number;
  };
  top_sport?: WrappedSportStat | null;
  sport_stats?: WrappedSportStat[];
  best_month?: WrappedMonth | null;
  monthly_series?: WrappedMonth[];
  fav_weekday?: { weekday: number; label: string; sessions: number } | null;
  longest_streak?: { days: number; start: string; end: string } | null;
  biggest_distance?: { sport: string; label: string; date: string; distance_km: number; duration_h: number } | null;
  longest_workout?: { sport: string; label: string; date: string; duration_h: number; distance_km: number } | null;
}

export async function fetchWrapped(year?: number): Promise<WrappedDashboard> {
  const url = year ? `/api/wrapped?year=${year}` : "/api/wrapped";
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export interface RaceFueling {
  estimated_duration_s: number;
  estimated_duration_label: string;
  prediction_source: string;
  pace_alvo_s_km: number | null;
  fluid_ml_per_h: number;
  fluid_total_ml: number;
  carbs_g_per_h: number;
  carbs_total_g: number;
  carbs_message: string;
  sodium_mg_per_h: number;
  splits: Array<{ km: number; cumulative_s: number }>;
}

export interface RaceRiegelPrediction {
  predicted_time_s: number;
  predicted_pace_s_km: number;
  confidence: string | null;
  based_on: { distance_m: number; duration_s: number; started_at: string };
}

export interface RaceReadinessComponent {
  name: string;
  score: number;
  weight: number;
  value: string | number;
  note: string;
}

export interface RaceReadiness {
  score: number;
  status: "pronta" | "boa" | "regular" | "precaucao";
  status_message: string;
  components: RaceReadinessComponent[];
}

export interface Race {
  id: number;
  name: string;
  race_date: string;
  sport: string;
  distance_m: number | null;
  triathlon_swim_m: number | null;
  triathlon_bike_m: number | null;
  triathlon_run_m: number | null;
  location: string | null;
  is_confirmed: number;
  days_to: number;
  weeks_to: number;
  phase: "base" | "build" | "peak" | "taper" | "race_week";
  phase_message: string;
  garmin_prediction: {
    predicted_time_s: number;
    predicted_pace_s_km: number;
    based_on_label: string;
    base_distance_m: number;
    approximation: boolean;
    scaled_via_riegel?: boolean;
  } | null;
  riegel_prediction: RaceRiegelPrediction | null;
  fueling: RaceFueling | null;
  readiness: RaceReadiness | null;
}

export interface CyclePhase {
  available: boolean;
  reason?: string;
  cycle_day?: number;
  phase?: "menstrual" | "folicular" | "ovulatoria" | "lutea";
  phase_label?: string;
  avg_cycle_length?: number;
  period_length?: number;
  next_period_estimated?: string;
  training_advice?: string;
  intensity_advice?: string;
  estimated_cycle?: boolean;
}

export interface CycleHistory {
  available: boolean;
  count?: number;
  avg_length?: number;
  min_length?: number;
  max_length?: number;
  variation_days?: number;
  regularity?: "regular" | "moderada" | "irregular";
  recent_cycles?: Array<{ start_date: string; actual_cycle_length: number | null }>;
}

export interface TrainingPlanSportSlot {
  sport: Sport;
  sessions: number;
  duration_min: number;
  distance_km: number;
}

export interface TrainingPlanKeySession {
  kind: string;
  label: string;
  target: string;
}

export type WorkoutBlock =
  | {
      block_type: "step";
      kind: string;
      end_label: string;
      duration_s: number;
      zone: string | null;
      pace: string | null;
      description: string | null;
      count: number;
    }
  | {
      block_type: "repeat";
      count: number;
      duration_s: number;
      children: WorkoutBlock[];
    };

export interface CoachExecution {
  completed: boolean;
  status: "completo" | "quase" | "parcial" | "iniciado" | "executado";
  status_label: string;
  completion_pct: number | null;
  activity_id: number;
  external_id: string;
  source: string;
  actual_duration_s: number;
  actual_distance_m: number;
  actual_pace_s_km: number | null;
  actual_avg_hr: number | null;
  actual_calories: number | null;
  started_at: string;
  notes: string[];
}

export interface CoachFueling {
  duration_label: string;
  pace_alvo_s_km: number | null;
  speed_alvo_kmh: number | null;
  fluid_ml_per_h: number;
  fluid_total_ml: number;
  carbs_g_per_h: number;
  carbs_total_g: number;
  carbs_message: string;
  sodium_mg_per_h: number;
}

export interface CoachWorkout {
  sport: "run" | "bike" | "swim" | "strength" | "yoga" | "walking" | "other";
  icon: string;
  kind: string;
  label: string;
  duration_min: number;
  distance_km: number | null;
  zone: string | null;
  target: string | null;
  is_race: boolean;
  blocks: WorkoutBlock[];
  has_structure: boolean;
  executed: CoachExecution | null;
  fueling: CoachFueling | null;
}

export interface CoachDay {
  day_idx: number;
  day_label: string;
  workouts: CoachWorkout[];
}

export interface CoachLoadComparison {
  prescribed_trimp: number;
  last_week_trimp: number;
  pct_of_last_week: number | null;
  message: string;
}

export interface CoachSchedule {
  week_start: string;
  available: boolean;
  days: CoachDay[];
  intensity_mix: { low: number; mid: number; high: number };
  totals: {
    sessions: number;
    duration_min: number;
    distance_km: number;
    by_sport: Record<string, number>;
  };
  load_comparison: CoachLoadComparison;
}

export interface CoachToday {
  date: string;
  workouts: CoachWorkout[];
}

export interface StrengthExercise {
  id: number;
  order_idx: number;
  name: string;
  sets: string | null;
  load_kg: number | null;
  load_text: string | null;
  rest_s: number | null;
  rest_text: string | null;
  instructions: string | null;
  is_warmup: boolean;
}

export interface StrengthRoutineSummary {
  id: number;
  name: string;
  order_idx: number;
  weekday: number | null;
  weekday_label: string | null;
  routine_label: string | null;
  fitness_level: string | null;
  source: string;
  source_file: string;
  exercise_count: number;
}

export interface StrengthRoutine extends StrengthRoutineSummary {
  exercises: StrengthExercise[];
}

export interface PMCPoint {
  date: string;
  load: number;
  ctl: number;
  atl: number;
  tsb: number;
}

export interface PMCDashboard {
  available: boolean;
  days: number;
  series: PMCPoint[];
  current?: PMCPoint;
  ctl_delta_4w?: number | null;
  zone?: "super_fresh" | "fresh" | "productive" | "overload" | "risk";
  zone_label?: string;
  message?: string;
}

export interface YoYSportCompare {
  sport: string;
  label: string;
  this_sessions: number;
  last_sessions: number;
  this_distance_km: number;
  last_distance_km: number;
  this_duration_min: number;
  last_duration_min: number;
  this_pace_s_km: number | null;
  last_pace_s_km: number | null;
  pace_delta_s: number | null;
}

export interface YoYPeriod {
  start: string;
  end: string;
  label: string;
  sessions: number;
  duration_min: number;
  distance_km: number;
  kcal: number;
}

export interface YearOverYear {
  available: boolean;
  this_period?: YoYPeriod;
  last_period?: YoYPeriod;
  deltas?: {
    sessions: number;
    duration_min: number;
    distance_km: number;
    kcal: number;
    sessions_pct: number | null;
    distance_pct: number | null;
  };
  by_sport_compare?: YoYSportCompare[];
}

export interface WellnessDay {
  date: string;
  body_battery: number | null;
  stress: number | null;
  rhr: number | null;
  hrv: number | null;
}

export interface WellnessDashboard {
  available: boolean;
  days: number;
  series: WellnessDay[];
  avg_body_battery?: number | null;
  avg_stress?: number | null;
  avg_rhr?: number | null;
  avg_hrv?: number | null;
  stress_high_days?: number;
  bb_low_days?: number;
}

export interface SleepNightDetail {
  date: string;
  total_min: number;
  deep_min: number;
  light_min: number;
  rem_min: number;
  awake_min: number;
  total_h: number;
  deep_pct: number;
  rem_pct: number;
  efficiency_pct: number | null;
  score: number | null;
}

export interface SleepDebt {
  available: boolean;
  days: number;
  nights_counted?: number;
  target_h: number;
  debt_h: number;
  avg_short_min_per_night?: number;
  status?: "ok" | "leve" | "moderada" | "alta";
  message?: string;
}

export interface SleepDetailDashboard {
  available: boolean;
  days: number;
  series: SleepNightDetail[];
  avg_total_h?: number;
  avg_total_min?: number;
  avg_deep_pct?: number;
  avg_rem_pct?: number;
  avg_efficiency_pct?: number | null;
  avg_score?: number | null;
  nights_short?: number;
  nights_low_score?: number;
  verdict?: "excelente" | "bom" | "regular" | "ruim";
  message?: string;
  sleep_debt?: SleepDebt;
}

export interface TemperatureTrendPoint {
  date: string;
  sport: string;
  avg_temp_c: number;
  max_temp_c: number;
  avg_hr: number | null;
  avg_pace_s_km: number | null;
}

export interface TemperatureTrend {
  available: boolean;
  reason?: string;
  days?: number;
  series?: TemperatureTrendPoint[];
  avg_temp_c?: number;
  max_temp_c?: number;
  hot_days_30plus?: number;
  cool_days_under20?: number;
  total_sessions?: number;
  insight?: string | null;
}

export interface VdotPace {
  key: string;
  label: string;
  pct_vdot: number;
  pace_s_km: number;
  description: string;
}

export interface VdotDashboard {
  available: boolean;
  reason?: string;
  vdot?: number;
  based_on?: { activity_id: number; started_at: string; distance_km: number; duration_s: number; pace_s_km: number | null };
  paces?: VdotPace[];
}

export interface CyclePhasePerformance {
  phase: "menstrual" | "folicular" | "ovulatoria" | "lutea";
  label: string;
  color: string;
  sessions: number;
  avg_duration_min: number;
  total_km: number;
  avg_pace_s_km: number | null;
  avg_hr: number | null;
}

export interface CyclePerformanceDashboard {
  available: boolean;
  reason?: string;
  days?: number;
  total_sessions_classified?: number;
  by_phase?: CyclePhasePerformance[];
  insights?: string[];
}

export interface CaloriesDay {
  date: string;
  total: number | null;
  active: number | null;
  bmr: number | null;
  bmr_per_hour?: number | null;
  workout_minutes?: number;
  workout_kcal?: number;
  workout_per_hour?: number | null;
}

export interface CaloriesBySport {
  sport: string;
  label: string;
  sessions: number;
  total_kcal: number;
  avg_per_session: number;
  avg_per_hour: number;
}

export interface CaloriesMacros {
  tdee_target: number;
  protein_g: number;
  protein_kcal: number;
  carb_g: number;
  carb_kcal: number;
  fat_g: number;
  fat_kcal: number;
  protein_pct: number;
  carb_pct: number;
  fat_pct: number;
}

export interface CaloriesReferences {
  available: boolean;
  bmr_garmin?: number | null;
  bmr_mifflin?: number;
  bmr_harris?: number;
  bmr_diff_garmin_vs_mifflin?: number | null;
  macros?: CaloriesMacros | null;
}

export interface CaloriesDashboard {
  available: boolean;
  days: number;
  current: CaloriesDay | null;
  average: { total: number | null; active: number | null; bmr: number | null };
  week_total_kcal: number;
  week_active_kcal: number;
  daily_series: CaloriesDay[];
  by_sport: CaloriesBySport[];
  references: CaloriesReferences;
}

export interface ProfileWeightPoint { date: string; kg: number }

export interface ProfileDashboard {
  available: boolean;
  age: number | null;
  gender: string | null;
  birth_date: string | null;
  max_hr_override: number | null;
  weight: {
    kg: number | null;
    date: string | null;
    first_kg: number | null;
    first_date: string | null;
    delta_kg: number | null;
    series: ProfileWeightPoint[];
  };
  height_cm: number | null;
  bmi: number | null;
  bmi_zone: "abaixo" | "saudavel" | "sobrepeso" | "obesidade" | null;
  vo2max: {
    value: number | null;
    date: string | null;
    first_value: number | null;
    first_date: string | null;
    delta: number | null;
  };
  ftp_watts: number | null;
  ftp_date: string | null;
}

export interface StrengthDashboard {
  available: boolean;
  today: StrengthRoutine | null;
  today_weekday_label: string;
  routines: StrengthRoutineSummary[];
}

export interface TrainingPlanDay {
  day_idx: number;
  day_label: string;
  sport: "run" | "bike" | "swim" | null;
  kind: string | null;
  label: string | null;
  duration_min: number;
  distance_km: number | null;
  zone: string | null;
  target: string | null;
  icon: string | null;
}

export interface TrainingPlan {
  week_start: string;
  phase: "base" | "build" | "peak" | "taper" | "race_week" | "manutencao";
  phase_reason: string;
  target_load_pct: number;
  target_reason: string;
  sessions_by_sport: TrainingPlanSportSlot[];
  intensity_mix: { low: number; mid: number; high: number };
  key_sessions: TrainingPlanKeySession[];
  rest_days: number;
  warnings: string[];
  polarization_now: string | null;
  last_week_load: { sessions: number; duration_min: number; distance_km: number };
  schedule: TrainingPlanDay[];
}

export interface CycleDashboard {
  current: CyclePhase;
  history: CycleHistory;
  recent_logs: Array<{ date: string; flow: string | null; symptoms: string[]; moods: string[]; ovulation_day: number }>;
}

export async function fetchRaces(): Promise<Race[]> {
  const r = await fetch("/api/races");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function fetchCycle(): Promise<CycleDashboard> {
  const r = await fetch("/api/cycle");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function fetchWeeklySummary(useAi: boolean): Promise<WeeklySummary> {
  const r = await fetch(`/api/weekly-summary?use_ai=${useAi}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function fetchDashboard(): Promise<Dashboard> {
  const res = await fetch("/api/dashboard");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface RefreshResult {
  ok: boolean;
  elapsed_s: number;
  results: Record<string, { inserted?: number; updated?: number; error?: string }>;
}

export async function triggerRefresh(): Promise<RefreshResult> {
  const res = await fetch("/api/refresh", { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function formatPace(secondsPerKm: number): string {
  const m = Math.floor(secondsPerKm / 60);
  const s = Math.round(secondsPerKm % 60);
  return `${m}:${String(s).padStart(2, "0")}/km`;
}

export function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (h > 0) return `${h}h${String(m).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatDistance(meters: number): string {
  if (meters >= 1000) return `${(meters / 1000).toFixed(meters % 1000 === 0 ? 0 : 1)}km`;
  return `${meters}m`;
}
