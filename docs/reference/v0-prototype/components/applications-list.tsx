import { useState, type KeyboardEvent } from "react"
import { Clock, Plus } from "lucide-react"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export const applicationsListData = {
  app: {
    name: "Job Tracker",
    nav: [
      { label: "Applications", href: "#", active: true },
      { label: "Resume", href: "#", active: false },
      { label: "Insights", href: "#", active: false },
    ],
  },
  stages: ["Saved", "Applied", "Screening", "Interviewing", "Offer", "Accepted", "Rejected", "Withdrawn"],
  inProgressStages: ["Applied", "Screening", "Interviewing"],
  staleThresholdDays: 14,
  applications: [
    { id: "northwind-freight", company: "Northwind Freight", role: "Senior Backend Engineer", source: "LinkedIn", stage: "Saved", resumeSent: "Not sent yet", lastActivity: "Nov 14", daysSinceActivity: 3 },
    { id: "larkspur-health", company: "Larkspur Health", role: "Staff Engineer, Platform", source: "Referral", stage: "Interviewing", resumeSent: "Tailored", lastActivity: "Nov 15", daysSinceActivity: 2 },
    { id: "tallgrass-payments", company: "Tallgrass Payments", role: "Senior Software Engineer", source: "Company site", stage: "Applied", resumeSent: "Tailored", lastActivity: "Nov 13", daysSinceActivity: 4 },
    { id: "brightwell-labs", company: "Brightwell Labs", role: "Senior Rails Engineer", source: "Recruiter", stage: "Screening", resumeSent: "Base", lastActivity: "Nov 12", daysSinceActivity: 5 },
    { id: "meridian-robotics", company: "Meridian Robotics", role: "Engineering Lead", source: "Referral", stage: "Interviewing", resumeSent: "Tailored", lastActivity: "Nov 10", daysSinceActivity: 7 },
    { id: "juniper-analytics", company: "Juniper Analytics", role: "Senior Software Engineer", source: "Other", stage: "Saved", resumeSent: "Not sent yet", lastActivity: "Nov 9", daysSinceActivity: 8 },
    { id: "ostrander-finch", company: "Ostrander & Finch", role: "Software Engineer", source: "Company site", stage: "Rejected", resumeSent: "Base", lastActivity: "Nov 3", daysSinceActivity: 14 },
    { id: "fernhill-logistics", company: "Fernhill Logistics", role: "Senior Backend Engineer", source: "LinkedIn", stage: "Applied", resumeSent: "Tailored", lastActivity: "Oct 30", daysSinceActivity: 18 },
    { id: "copperline-energy", company: "Copperline Energy", role: "Backend Engineer", source: "LinkedIn", stage: "Applied", resumeSent: "Base", lastActivity: "Oct 28", daysSinceActivity: 20 },
    { id: "palisade-software", company: "Palisade Software", role: "Senior Engineer", source: "Recruiter", stage: "Withdrawn", resumeSent: "Base", lastActivity: "Oct 21", daysSinceActivity: 27 },
  ],
}

type ApplicationsListData = typeof applicationsListData
type ApplicationRow = ApplicationsListData["applications"][number]

const stageBadgeStyles: Record<string, string> = {
  Saved: "border-transparent bg-indigo-100 text-indigo-800",
  Applied: "border-transparent bg-blue-100 text-blue-800",
  Screening: "border-transparent bg-blue-100 text-blue-800",
  Interviewing: "border-transparent bg-blue-100 text-blue-800",
  Offer: "border-transparent bg-green-100 text-green-800",
  Accepted: "border-transparent bg-green-100 text-green-800",
  Rejected: "border-border bg-muted text-muted-foreground",
  Withdrawn: "border-dashed border-muted-foreground/60 bg-background text-muted-foreground",
}

const columns = ["Company", "Role", "Source", "Stage", "Resume sent", "Last activity"]

export default function ApplicationsList({
  data = applicationsListData,
  onOpenApplication,
  onNewApplication,
  onNavigate,
}: {
  data?: ApplicationsListData
  onOpenApplication?: (id: string) => void
  onNewApplication?: () => void
  onNavigate?: (label: string) => void
}) {
  const { app, stages, inProgressStages, staleThresholdDays, applications } = data
  const [activeFilter, setActiveFilter] = useState("All")

  const isStale = (row: ApplicationRow) =>
    inProgressStages.includes(row.stage) && row.daysSinceActivity >= staleThresholdDays

  const countFor = (stage: string) => applications.filter((row) => row.stage === stage).length
  const inProgressCount = applications.filter((row) => inProgressStages.includes(row.stage)).length
  const staleCount = applications.filter(isStale).length
  const filters = [{ label: "All", count: applications.length }, ...stages.map((stage) => ({ label: stage, count: countFor(stage) }))]
  const visibleRows = activeFilter === "All" ? applications : applications.filter((row) => row.stage === activeFilter)

  function handleRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, id: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      onOpenApplication?.(id)
    }
  }

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

      <main className="mx-auto flex max-w-6xl flex-col gap-5 px-4 py-8 sm:px-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Applications</h1>
            <p className="text-sm text-muted-foreground">
              {applications.length} applications · {inProgressCount} in progress
            </p>
          </div>
          <Button size="lg" className="w-fit" onClick={onNewApplication}>
            <Plus className="size-4" aria-hidden="true" />
            New application
          </Button>
        </div>

        <div role="group" aria-label="Filter by stage" className="flex flex-wrap gap-2">
          {filters.map((filter) => {
            const active = filter.label === activeFilter
            return (
              <button
                key={filter.label}
                type="button"
                aria-pressed={active}
                onClick={() => setActiveFilter(filter.label)}
                className={cn(
                  "inline-flex h-10 items-center gap-2 rounded-full border px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  active
                    ? "border-foreground bg-foreground text-background"
                    : "bg-background text-foreground hover:bg-muted",
                )}
              >
                {filter.label}
                <span className={cn("font-normal", active ? "text-background/80" : "text-muted-foreground")}>
                  {filter.count}
                </span>
              </button>
            )
          })}
        </div>

        {staleCount > 0 && (
          <div
            role="status"
            className="flex items-center gap-3 rounded-md border border-amber-400 bg-amber-50 px-4 py-3 text-sm text-amber-900"
          >
            <Clock className="size-4 shrink-0" aria-hidden="true" />
            <p>
              {staleCount} {staleCount === 1 ? "application has" : "applications have"} had no activity in{" "}
              {staleThresholdDays} or more days.
            </p>
          </div>
        )}

        <div className="overflow-x-auto rounded-lg border bg-background">
          <table className="w-full min-w-[56rem] text-left text-sm">
            <caption className="sr-only">
              {activeFilter === "All" ? "All applications" : `${activeFilter} applications`}
            </caption>
            <thead className="border-b bg-muted/40">
              <tr>
                {columns.map((column) => (
                  <th
                    key={column}
                    scope="col"
                    className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleRows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} className="px-4 py-10 text-center text-muted-foreground">
                    No applications in {activeFilter}.
                  </td>
                </tr>
              ) : (
                visibleRows.map((row) => (
                  <tr
                    key={row.id}
                    tabIndex={0}
                    onClick={() => onOpenApplication?.(row.id)}
                    onKeyDown={(event) => handleRowKeyDown(event, row.id)}
                    aria-label={`Open ${row.company}, ${row.role}`}
                    className="cursor-pointer border-b transition-colors last:border-b-0 hover:bg-muted/40 focus-visible:bg-muted/60 focus-visible:outline-none"
                  >
                    <th scope="row" className="px-4 py-3.5 font-semibold">
                      {row.company}
                    </th>
                    <td className="px-4 py-3.5">{row.role}</td>
                    <td className="px-4 py-3.5">{row.source}</td>
                    <td className="px-4 py-3.5">
                      <Badge variant="outline" className={cn("font-semibold", stageBadgeStyles[row.stage])}>
                        {row.stage}
                      </Badge>
                    </td>
                    <td className="px-4 py-3.5">{row.resumeSent}</td>
                    <td className="px-4 py-3.5">
                      <span className="flex items-center gap-2 whitespace-nowrap">
                        {row.lastActivity}
                        {isStale(row) && (
                          <Badge
                            variant="outline"
                            className="border-amber-500 bg-amber-50 font-semibold text-amber-800"
                          >
                            Stale, {row.daysSinceActivity} days
                          </Badge>
                        )}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  )
}
