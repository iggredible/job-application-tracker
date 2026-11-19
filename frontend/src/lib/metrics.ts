import type { Stage } from '@/lib/applications'

// The shapes of GET /metrics/pipeline and GET /metrics/ai. Every number is calculated by the API
// on request; this file only names them and turns them into text.

export interface FunnelStep {
  stage: Stage
  count: number
  /** 0 to 1. Null for the first stage, and when the stage before is empty. */
  share_of_previous: number | null
}

export interface StageDuration {
  stage: Stage
  /** Null when no interval was completed. */
  median_days: number | null
  sample_size: number
}

export interface ResponseRate {
  applied: number
  responses: number
  /** 0 to 1. Null when none applied. */
  rate: number | null
}

export interface PipelineMetrics {
  total_applications: number
  applied_applications: number
  funnel: FunnelStep[]
  time_in_stage: StageDuration[]
  response: ResponseRate
  stale_applications: number
  resume_comparison: { tailored: ResponseRate; base: ResponseRate }
}

export type AIFeature = 'posting_analysis' | 'tailor_resume'

export interface AIMetricsRow {
  feature: AIFeature
  prompt_version: string
  model: string
  calls: number
  failed_calls: number
  approved_as_is: number
  edited_then_approved: number | null
  rejected: number
  pending: number
  superseded: number
  avg_edit_ratio: number | null
  avg_flags_per_draft: number | null
  input_tokens: number
  output_tokens: number
  /** USD. */
  estimated_cost: number
  median_latency_ms: number
}

export interface AIMetrics {
  rows: AIMetricsRow[]
}

/** Shown wherever a value does not apply or could not be worked out. */
export const NA = 'n/a'

export function featureLabel(feature: AIFeature): string {
  return feature === 'posting_analysis' ? 'Posting analysis' : 'Tailor resume'
}

/** A share from 0 to 1 as a whole percent. */
export function formatPercent(value: number | null): string {
  return value === null ? NA : `${Math.round(value * 100)}%`
}

/** Days to one decimal, without a trailing ".0". */
export function formatDays(days: number | null): string {
  if (days === null) return NA
  const rounded = Number(days.toFixed(1))
  return `${rounded} ${rounded === 1 ? 'day' : 'days'}`
}

export function formatDecimal(value: number | null): string {
  return value === null ? NA : value.toFixed(1)
}

export function formatCost(usd: number): string {
  return `$${usd.toFixed(2)}`
}

export function formatLatency(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`
}

export function formatCount(value: number | null): string {
  return value === null ? NA : String(value)
}
