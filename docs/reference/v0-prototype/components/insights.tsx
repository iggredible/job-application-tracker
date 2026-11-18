import type { ReactNode } from "react"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export const insightsData = {
  app: {
    name: "Job Tracker",
    nav: [
      { label: "Applications", href: "#", active: false },
      { label: "Resume", href: "#", active: false },
      { label: "Insights", href: "#", active: true },
    ],
  },
  page: {
    title: "Insights",
    description:
      "Calculated on request from the timeline and the AI call log. Nothing here is a stored number.",
  },
  jobSearch: {
    tracked: 40,
    applied: 34,
    responded: 19,
    stale: 5,
    staleThresholdDays: 14,
    funnel: [
      { stage: "Applied", count: 34 },
      { stage: "Screening", count: 14 },
      { stage: "Interviewing", count: 8 },
      { stage: "Offer", count: 2 },
    ],
    timeInStage: [
      { stage: "Saved", medianDays: 2, sample: 34 },
      { stage: "Applied", medianDays: 9, sample: 27 },
      { stage: "Screening", medianDays: 6, sample: 11 },
      { stage: "Interviewing", medianDays: 12, sample: 6 },
      { stage: "Offer", medianDays: 4, sample: 2 },
    ],
    resumeComparison: [
      { resume: "Tailored", applied: 18, responses: 12 },
      { resume: "Base", applied: 16, responses: 7 },
    ],
  },
  aiCalls: [
    {
      feature: "Posting analysis",
      prompt: "v1",
      calls: 24,
      failed: 1,
      approvedAsIs: 19,
      editedApproved: null,
      rejected: 3,
      pending: 1,
      editRatio: null,
      flagsPerDraft: null,
      costUsd: 0.31,
      medianLatencySec: 4.2,
    },
    {
      feature: "Tailor resume",
      prompt: "v1",
      calls: 12,
      failed: 0,
      approvedAsIs: 2,
      editedApproved: 6,
      rejected: 3,
      pending: 1,
      editRatio: 0.31,
      flagsPerDraft: 1.8,
      costUsd: 0.52,
      medianLatencySec: 9.6,
    },
    {
      feature: "Tailor resume",
      prompt: "v2",
      calls: 14,
      failed: 1,
      approvedAsIs: 6,
      editedApproved: 5,
      rejected: 1,
      pending: 1,
      editRatio: 0.14,
      flagsPerDraft: 0.4,
      costUsd: 0.63,
      medianLatencySec: 9.1,
    },
  ] as AiCallRow[],
}

type AiCallRow = {
  feature: string
  prompt: string
  calls: number
  failed: number
  approvedAsIs: number
  editedApproved: number | null
  rejected: number
  pending: number
  editRatio: number | null
  flagsPerDraft: number | null
  costUsd: number
  medianLatencySec: number
}

type InsightsData = typeof insightsData

function percent(part: number, whole: number) {
  return whole === 0 ? 0 : Math.round((part / whole) * 100)
}

function orNA(value: number | null, format: (value: number) => string = String) {
  return value === null ? "n/a" : format(value)
}

const headCell = "py-3 text-xs font-medium uppercase tracking-wide text-muted-foreground"
const bodyCell = "py-3.5 text-sm"

function SectionHeading({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h2 id={id} className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      {children}
    </h2>
  )
}

function StatCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Card className="gap-0 py-5">
      <CardContent className="flex flex-col gap-1 px-5">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-4xl font-semibold tracking-tight">{value}</p>
        <p className="text-sm text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  )
}

function PanelHeader({ title, description }: { title: string; description: string }) {
  return (
    <CardHeader className="gap-1 px-5">
      <CardTitle className="text-base">{title}</CardTitle>
      <CardDescription>{description}</CardDescription>
    </CardHeader>
  )
}

function FunnelCard({ funnel }: { funnel: InsightsData["jobSearch"]["funnel"] }) {
  const max = Math.max(...funnel.map((step) => step.count), 1)

  return (
    <Card className="gap-5 py-5">
      <PanelHeader
        title="Funnel"
        description="Applications that reached each stage, and the share that moved on from the stage before"
      />
      <CardContent className="px-5">
        <ul className="flex flex-col gap-3">
          {funnel.map((step, index) => {
            const previous = funnel[index - 1]
            return (
              <li
                key={step.stage}
                className="grid grid-cols-[6rem_minmax(0,1fr)] items-center gap-x-4 gap-y-1 sm:grid-cols-[6.5rem_minmax(0,1fr)_8.5rem]"
              >
                <span className="text-sm">{step.stage}</span>
                <div className="h-5" aria-hidden="true">
                  <div
                    className="h-full rounded-sm bg-blue-800 dark:bg-blue-500"
                    style={{ width: `${(step.count / max) * 100}%`, minWidth: step.count ? "0.5rem" : 0 }}
                  />
                </div>
                <span className="col-start-2 text-sm sm:col-start-auto">
                  <span className="font-semibold">{step.count}</span>
                  {previous ? (
                    <span className="text-xs text-muted-foreground">
                      {" "}
                      {percent(step.count, previous.count)}% moved on
                    </span>
                  ) : null}
                </span>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

function TimeInStageCard({ rows }: { rows: InsightsData["jobSearch"]["timeInStage"] }) {
  return (
    <Card className="gap-4 py-5">
      <PanelHeader title="Time in stage" description="Median days before moving on" />
      <CardContent className="px-5">
        <table className="w-full">
          <thead>
            <tr className="border-b text-left">
              <th scope="col" className={headCell}>Stage</th>
              <th scope="col" className={cn(headCell, "text-right")}>Median</th>
              <th scope="col" className={cn(headCell, "w-24 text-right")}>Sample</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.stage} className="border-b last:border-0">
                <th scope="row" className={cn(bodyCell, "text-left font-normal")}>{row.stage}</th>
                <td className={cn(bodyCell, "text-right font-semibold")}>
                  {row.medianDays} {row.medianDays === 1 ? "day" : "days"}
                </td>
                <td className={cn(bodyCell, "text-right text-muted-foreground")}>{row.sample}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

function ResumeComparisonCard({ rows }: { rows: InsightsData["jobSearch"]["resumeComparison"] }) {
  return (
    <Card className="gap-4 py-5">
      <PanelHeader
        title="Tailored vs base resume"
        description="Response rate by which resume was sent. Small samples: read the difference as a hint, not proof."
      />
      <CardContent className="overflow-x-auto px-5">
        <table className="w-full min-w-[28rem]">
          <thead>
            <tr className="border-b text-left">
              <th scope="col" className={headCell}>Resume sent</th>
              <th scope="col" className={cn(headCell, "text-right")}>Applied</th>
              <th scope="col" className={cn(headCell, "text-right")}>Responses</th>
              <th scope="col" className={cn(headCell, "text-right")}>Response rate</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.resume} className="border-b last:border-0">
                <th scope="row" className={cn(bodyCell, "text-left font-normal")}>{row.resume}</th>
                <td className={cn(bodyCell, "text-right")}>{row.applied}</td>
                <td className={cn(bodyCell, "text-right")}>{row.responses}</td>
                <td className={cn(bodyCell, "text-right font-semibold")}>
                  {percent(row.responses, row.applied)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

function AiCallsCard({ rows }: { rows: AiCallRow[] }) {
  const columns = [
    "Calls",
    "Failed",
    "Approved as is",
    "Edited, approved",
    "Rejected",
    "Pending",
    "Edit ratio",
    "Flags per draft",
    "Est. cost",
    "Median latency",
  ]

  return (
    <Card className="gap-4 py-5">
      <PanelHeader
        title="AI calls by feature and prompt version"
        description="From the call log and the drafts each call produced. Lower edit ratio and fewer flags mean drafts needed less fixing."
      />
      <CardContent className="overflow-x-auto px-5">
        <table className="w-full min-w-[60rem]">
          <thead>
            <tr className="border-b text-left">
              <th scope="col" className={headCell}>Feature</th>
              <th scope="col" className={headCell}>Prompt</th>
              {columns.map((column) => (
                <th key={column} scope="col" className={cn(headCell, "max-w-24 pl-4 text-right leading-snug")}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.feature}-${row.prompt}`} className="border-b last:border-0">
                <th scope="row" className={cn(bodyCell, "max-w-28 pr-4 text-left font-normal")}>
                  {row.feature}
                </th>
                <td className={bodyCell}>
                  <Badge variant="secondary" className="font-mono text-xs font-normal">
                    {row.prompt}
                  </Badge>
                </td>
                <td className={cn(bodyCell, "text-right")}>{row.calls}</td>
                <td className={cn(bodyCell, "text-right")}>{row.failed}</td>
                <td className={cn(bodyCell, "text-right")}>{row.approvedAsIs}</td>
                <td className={cn(bodyCell, "text-right", row.editedApproved === null && "text-muted-foreground")}>
                  {orNA(row.editedApproved)}
                </td>
                <td className={cn(bodyCell, "text-right")}>{row.rejected}</td>
                <td className={cn(bodyCell, "text-right")}>{row.pending}</td>
                <td
                  className={cn(
                    bodyCell,
                    "text-right",
                    row.editRatio === null ? "text-muted-foreground" : "font-semibold",
                  )}
                >
                  {orNA(row.editRatio, (value) => `${Math.round(value * 100)}%`)}
                </td>
                <td
                  className={cn(
                    bodyCell,
                    "text-right",
                    row.flagsPerDraft === null ? "text-muted-foreground" : "font-semibold",
                  )}
                >
                  {orNA(row.flagsPerDraft, (value) => value.toFixed(1))}
                </td>
                <td className={cn(bodyCell, "text-right")}>${row.costUsd.toFixed(2)}</td>
                <td className={cn(bodyCell, "text-right")}>{row.medianLatencySec.toFixed(1)} s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

export default function Insights({
  data = insightsData,
  onNavigate,
}: {
  data?: InsightsData
  onNavigate?: (label: string) => void
}) {
  const { app, page, jobSearch, aiCalls } = data

  return (
    <div className="min-h-screen bg-muted/30 text-foreground">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-6xl items-center gap-8 px-4 sm:px-6">
          <span className="py-4 text-base font-semibold">{app.name}</span>
          <nav aria-label="Main" className="flex gap-6 overflow-x-auto">
            {app.nav.map((item) => (
              <a
                key={item.label}
                href={item.href}
                aria-current={item.active ? "page" : undefined}
                onClick={(event) => {
                  if (!onNavigate) return
                  event.preventDefault()
                  onNavigate(item.label)
                }}
                className={cn(
                  "border-b-2 py-4 text-sm transition-colors",
                  item.active
                    ? "border-foreground font-medium text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{page.title}</h1>
          <p className="text-sm text-muted-foreground">{page.description}</p>
        </div>

        <section aria-labelledby="job-search-heading" className="flex flex-col gap-5">
          <SectionHeading id="job-search-heading">Job search</SectionHeading>

          <div className="grid gap-4 md:grid-cols-3">
            <StatCard
              label="Applied"
              value={String(jobSearch.applied)}
              detail={`of ${jobSearch.tracked} tracked applications`}
            />
            <StatCard
              label="Response rate"
              value={`${percent(jobSearch.responded, jobSearch.applied)}%`}
              detail={`${jobSearch.responded} of ${jobSearch.applied} applied got a response`}
            />
            <StatCard
              label="Stale applications"
              value={String(jobSearch.stale)}
              detail={`no activity in ${jobSearch.staleThresholdDays} or more days`}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <FunnelCard funnel={jobSearch.funnel} />
            <TimeInStageCard rows={jobSearch.timeInStage} />
          </div>

          <ResumeComparisonCard rows={jobSearch.resumeComparison} />
        </section>

        <section aria-labelledby="ai-performance-heading" className="flex flex-col gap-5">
          <SectionHeading id="ai-performance-heading">AI performance</SectionHeading>
          <AiCallsCard rows={aiCalls} />
        </section>
      </main>
    </div>
  )
}
