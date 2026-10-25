export interface HourlyRecord {
  startTime: string
  generation: number
}

export interface ActualsResponse {
  date: string
  resolution: string
  records: HourlyRecord[]
}

export interface ForecastResponse {
  date: string
  vintage: string
  gate_closure: string
  records: HourlyRecord[]
}

export interface DailyAccuracy {
  date: string
  mae: number
  rmse: number
  mape: number
  mape_excluded_slots: number
  mean_bias?: number
}

export interface MonthlyAccuracy {
  mae: number
  rmse: number
  mape: number
}

export interface AccuracyResponse {
  monthly: MonthlyAccuracy
  daily: DailyAccuracy[]
  insight: string
}

export interface HealthResponse {
  status: string
  db: string
}
