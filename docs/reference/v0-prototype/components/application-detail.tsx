import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react"
import { ArrowLeft, Check, ChevronDown, Lock, TriangleAlert, X } from "lucide-react"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"

export const applicationData = {
  app: {
    name: "Job Tracker",
    nav: [
      { label: "Applications", href: "#", active: true },
      { label: "Resume", href: "#", active: false },
      { label: "Insights", href: "#", active: false },
    ],
  },
  backLink: { label: "All applications", href: "#" },
  application: {
    company: "Northwind Freight",
    stage: "Saved",
    meta: ["Senior Backend Engineer", "Source: LinkedIn", "Added Nov 12"],
    nextStagesByStage: {
      Saved: ["Applied", "Withdrawn"],
      Applied: ["Screening", "Rejected", "Withdrawn"],
    } as Record<string, string[]>,
  },
  steps: {
    analysis: { number: 1, title: "Posting analysis" },
    resume: { number: 2, title: "Tailored resume" },
    applied: { number: 3, title: "Mark as applied" },
  },
  posting: {
    originalUrl: "#",
    title: "Senior Backend Engineer, Carrier Platform",
    intro:
      "Northwind Freight builds software that connects shippers with regional carriers. The Carrier Platform team owns the services that book, track and settle every load.",
    sections: [
      {
        heading: "What you will do",
        body: "Design and run Ruby on Rails services backed by PostgreSQL. Build REST APIs and third-party integrations with carrier and accounting systems. Move long-running work into background jobs. Lead a small team and set review standards.",
      },
      {
        heading: "What we are looking for",
        body: "Deep experience with Ruby on Rails and PostgreSQL. Experience leading engineers. Comfortable with CI/CD. Experience with AWS and Kubernetes is a plus. React experience is a plus.",
      },
    ],
  },
  analysis: {
    status: "draft" as ReviewStatus,
    meta: ["Prompt v1", "Generated Nov 16"],
    reviewHint:
      "Check that the requirements and keywords match the posting. Tailoring uses the approved keywords.",
    rejectedHint: "You rejected this analysis. Analyze again to get a new draft.",
    mustHave: [
      "Ruby on Rails services in production",
      "PostgreSQL",
      "REST APIs and third-party integrations",
      "Experience leading engineers",
    ],
    niceToHave: ["CI/CD", "AWS and Kubernetes", "React"],
    coverage: { covered: 6, total: 10 },
    coveredKeywords: [
      "ruby on rails",
      "postgresql",
      "rest apis",
      "background jobs",
      "integrations",
      "team leadership",
    ],
    missingKeywords: ["ci/cd", "aws", "kubernetes", "react"],
  },
  tailoredResume: {
    lockedNote: "Approve the posting analysis to unlock tailoring.",
    meta: ["Prompt v1", "2 past examples used", "Generated Nov 16"],
    approvedHint: "Approved. Pick it in step 3 when you apply.",
    rejectedHint: "You rejected this draft. Tailor again to get a new one.",
    flags: [
      "Number \u201c40%\u201d in \u201cCut report run time by 40%\u2026\u201d",
      "Skill \u201cKubernetes\u201d",
    ],
    flagsNote: "Edit or remove them, or keep them if they are true. Flags do not block approval.",
    baseResume: `# Jordan Avery
Lead Software Engineer · Austin, TX

## Experience
### Lead Software Engineer – Coldline Logistics (Jun 2021 – May 2026)
– Led a team of 5 building shipment tracking and order management in Rails
– Built NetSuite integrations between internal systems
– Moved slow reports to background jobs with Sidekiq
– Maintained CI pipelines and code review standards

### Software Engineer – Harbor Mortgage (2018 – 2021)
– Built REST APIs on Rails and PostgreSQL for loan servicing

## Skills
Ruby on Rails, PostgreSQL, Sidekiq, REST APIs, NetSuite, RSpec`,
    draft: `# Jordan Avery
Lead Software Engineer · Austin, TX

## Summary
Backend lead on Ruby on Rails and PostgreSQL, focused on third-party integrations and order workflows.

## Experience
### Lead Software Engineer – Coldline Logistics (Jun 2021 – May 2026)
– Led a team of 5 delivering shipment tracking and order management services on Ruby on Rails
– Designed third-party integrations between NetSuite and internal systems over REST APIs
– Cut report run time by 40% by moving work to Sidekiq background jobs
– Maintained CI/CD pipelines and code review standards

### Software Engineer – Harbor Mortgage (2018 – 2021)
– Built REST APIs on Rails and PostgreSQL for loan servicing

## Skills
Ruby on Rails, PostgreSQL, REST APIs, Sidekiq, NetSuite, Kubernetes`,
    coverageChange: { from: 60, to: 80 },
    newlyCovered: ["ci/cd", "kubernetes"],
    stillMissing: ["aws", "react"],
  },
  markApplied: {
    description: "Do this after you have submitted the application on the company\u2019s site.",
    question: "Which resume did you send?",
    options: [
      { id: "base", label: "Base resume", meta: "Last saved Nov 12 · coverage 60%" },
      { id: "tailored", label: "Tailored resume", meta: "Approved draft · coverage 80%" },
    ],
    footnote:
      "Moves the application from Saved to Applied, records today as the applied date and adds a timeline entry. The app does not submit anything for you.",
  },
  timeline: [{ id: "t1", date: "Nov 12, 4:35 PM", type: "Stage change", text: "Created in Saved" }],
}

type ReviewStatus = "draft" | "approved" | "rejected"
type StepStatus = "done" | "current" | "upcoming"
type ApplicationData = typeof applicationData
type TimelineEntry = ApplicationData["timeline"][number]

const SIMULATED_RUN_MS = 1200

const stageBadgeClass: Record<string, string> = {
  Saved: "bg-indigo-100 text-indigo-800 hover:bg-indigo-100",
  Applied: "bg-blue-100 text-blue-800 hover:bg-blue-100",
}

function formatNow() {
  const now = new Date()
  const date = now.toLocaleDateString("en-US", { month: "short", day: "numeric" })
  const time = now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
  return `${date}, ${time}`
}

export default function ApplicationDetail({
  data = applicationData,
  onBack,
  onNavigate,
}: {
  data?: ApplicationData
  onBack?: () => void
  onNavigate?: (label: string) => void
}) {
  const { app, backLink, application, steps, posting, analysis, tailoredResume, markApplied } = data

  const [stage, setStage] = useState(application.stage)
  const [analysisStatus, setAnalysisStatus] = useState<ReviewStatus>(analysis.status)
  const [analysisMeta, setAnalysisMeta] = useState(analysis.meta)
  const [analyzing, setAnalyzing] = useState(false)
  const [resumeStatus, setResumeStatus] = useState<ReviewStatus>("draft")
  const [resumeMeta, setResumeMeta] = useState(tailoredResume.meta)
  const [tailoring, setTailoring] = useState(false)
  const [draft, setDraft] = useState(tailoredResume.draft)
  const [sentResumeId, setSentResumeId] = useState("")
  const [note, setNote] = useState("")
  const [timeline, setTimeline] = useState<TimelineEntry[]>(data.timeline)
  const timers = useRef<number[]>([])

  useEffect(() => () => timers.current.forEach((id) => window.clearTimeout(id)), [])

  const isApplied = stage !== application.stage
  const resumeUnlocked = analysisStatus === "approved"
  const resumeApproved = resumeUnlocked && resumeStatus === "approved"
  const coveragePercent = Math.round((analysis.coverage.covered / analysis.coverage.total) * 100)
  const nextStages = application.nextStagesByStage[stage] ?? []
  const resumeOptions = markApplied.options.filter((option) => option.id !== "tailored" || resumeApproved)
  const sentResume = resumeOptions.find((option) => option.id === sentResumeId)

  const stepItems: { number: number; title: string; subtitle: string; status: StepStatus }[] = [
    {
      ...steps.analysis,
      status: analysisStatus === "approved" ? "done" : "current",
      subtitle: analyzing
        ? "Analyzing the posting\u2026"
        : { draft: "Draft waiting for your review", approved: "Approved", rejected: "Rejected, analyze again" }[
            analysisStatus
          ],
    },
    {
      ...steps.resume,
      status: !resumeUnlocked ? "upcoming" : resumeStatus === "approved" ? "done" : "current",
      subtitle: !resumeUnlocked
        ? "Locked until the analysis is approved"
        : tailoring
          ? "Tailoring your resume\u2026"
          : { draft: "Draft waiting for your review", approved: "Approved", rejected: "Rejected, tailor again" }[
              resumeStatus
            ],
    },
    {
      ...steps.applied,
      status: isApplied ? "done" : resumeApproved ? "current" : "upcoming",
      subtitle: isApplied && sentResume ? `Applied with ${sentResume.label.toLowerCase()}` : "Pick the resume you sent",
    },
  ]

  function addTimelineEntry(type: string, text: string) {
    setTimeline((entries) => [{ id: crypto.randomUUID(), date: formatNow(), type, text }, ...entries])
  }

  function simulate(setBusy: (busy: boolean) => void, onDone: () => void) {
    setBusy(true)
    const id = window.setTimeout(() => {
      onDone()
      setBusy(false)
    }, SIMULATED_RUN_MS)
    timers.current.push(id)
  }

  function handleAnalyzeAgain() {
    simulate(setAnalyzing, () => {
      setAnalysisStatus("draft")
      setAnalysisMeta([analysis.meta[0], "Generated just now"])
      setResumeStatus("draft")
      setDraft(tailoredResume.draft)
      if (sentResumeId === "tailored") setSentResumeId("")
    })
  }

  function handleApproveAnalysis() {
    setAnalysisStatus("approved")
    setResumeStatus("draft")
    addTimelineEntry("Review", "Posting analysis approved")
  }

  function handleRejectAnalysis() {
    setAnalysisStatus("rejected")
    addTimelineEntry("Review", "Posting analysis rejected")
  }

  function handleTailorAgain() {
    simulate(setTailoring, () => {
      setResumeStatus("draft")
      setDraft(tailoredResume.draft)
      setResumeMeta([tailoredResume.meta[0], tailoredResume.meta[1], "Generated just now"])
      if (sentResumeId === "tailored") setSentResumeId("")
    })
  }

  function handleApproveResume() {
    setResumeStatus("approved")
    addTimelineEntry("Review", "Tailored resume approved")
  }

  function handleRejectResume() {
    setResumeStatus("rejected")
    if (sentResumeId === "tailored") setSentResumeId("")
    addTimelineEntry("Review", "Tailored resume rejected")
  }

  function handleMarkApplied() {
    if (!sentResume) return
    setStage("Applied")
    addTimelineEntry("Stage change", `${stage} \u2192 Applied, sent ${sentResume.label.toLowerCase()}`)
  }

  function handleAddNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = note.trim()
    if (!text) return
    addTimelineEntry("Note", text)
    setNote("")
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

      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6">
        <a
          href={backLink.href}
          onClick={(event) => {
            if (!onBack) return
            event.preventDefault()
            onBack()
          }}
          className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          {backLink.label}
        </a>

        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
                {application.company}
              </h1>
              <Badge className={cn("border-transparent", stageBadgeClass[stage] ?? "bg-muted text-foreground")}>
                {stage}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">{application.meta.join(" · ")}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {isApplied ? `Next: ${nextStages.join(" or ")}` : "Apply in step 3 below"}
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="outline" />}>
                Change stage
                <ChevronDown className="size-4" aria-hidden="true" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {nextStages.map((nextStage) => (
                  <DropdownMenuItem key={nextStage}>{nextStage}</DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button variant="outline">Edit</Button>
          </div>
        </div>

        <ol className="grid gap-3 md:grid-cols-3" aria-label="Application progress">
          {stepItems.map((step) => (
            <li
              key={step.number}
              aria-current={step.status === "current" ? "step" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg bg-background p-4",
                step.status === "done" && "border",
                step.status === "current" && "border-2 border-foreground",
                step.status === "upcoming" && "border border-dashed",
              )}
            >
              <span
                className={cn(
                  "flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold",
                  step.status === "done" && "bg-green-700 text-white",
                  step.status === "current" && "bg-foreground text-background",
                  step.status === "upcoming" && "border text-muted-foreground",
                )}
              >
                {step.status === "done" ? (
                  <>
                    <Check className="size-4" aria-hidden="true" />
                    <span className="sr-only">Completed</span>
                  </>
                ) : (
                  step.number
                )}
              </span>
              <div className="flex flex-col">
                <span className="text-sm font-semibold">
                  {step.number}. {step.title}
                </span>
                <span className="text-sm text-muted-foreground" aria-live="polite">
                  {step.subtitle}
                </span>
              </div>
            </li>
          ))}
        </ol>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle className="text-lg">Job posting</CardTitle>
              <a href={posting.originalUrl} className="text-sm underline underline-offset-4 hover:text-muted-foreground">
                Open original
              </a>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col">
              <article className="flex flex-1 flex-col gap-4 rounded-md border bg-muted/40 p-5 text-sm leading-relaxed">
                <h3 className="font-semibold">{posting.title}</h3>
                <p>{posting.intro}</p>
                {posting.sections.map((section) => (
                  <section key={section.heading} className="flex flex-col gap-3">
                    <h4 className="font-semibold">{section.heading}</h4>
                    <p>{section.body}</p>
                  </section>
                ))}
              </article>
            </CardContent>
          </Card>

          <Card aria-busy={analyzing}>
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-lg">Posting analysis</CardTitle>
                <ReviewBadge status={analysisStatus} />
                {analysisStatus !== "approved" && (
                  <span className="text-sm text-muted-foreground">{analysisMeta.join(" · ")}</span>
                )}
              </div>
              {analysisStatus === "approved" && (
                <Button variant="outline" onClick={handleAnalyzeAgain} disabled={analyzing}>
                  {analyzing ? "Analyzing\u2026" : "Analyze again"}
                </Button>
              )}
            </CardHeader>
            <CardContent className={cn("flex flex-col gap-5 transition-opacity", analyzing && "opacity-50")}>
              <div className="grid gap-6 sm:grid-cols-2">
                <KeywordList title="Must have" items={analysis.mustHave} />
                <KeywordList title="Nice to have" items={analysis.niceToHave} />
              </div>

              <Separator />

              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-semibold">Keyword coverage, base resume</span>
                  <span>
                    <span className="font-semibold">{coveragePercent}%</span>{" "}
                    <span className="text-muted-foreground">
                      ({analysis.coverage.covered} of {analysis.coverage.total})
                    </span>
                  </span>
                </div>
                <Progress value={coveragePercent} aria-label="Keyword coverage" className="h-2" />
              </div>

              <ChipGroup label="Covered" items={analysis.coveredKeywords} />
              <ChipGroup label="Missing" items={analysis.missingKeywords} dashed />

              {analysisStatus !== "approved" && (
                <>
                  <Separator />
                  <div className="flex flex-col gap-4">
                    <p className="text-sm text-muted-foreground">
                      {analysisStatus === "rejected" ? analysis.rejectedHint : analysis.reviewHint}
                    </p>
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button variant="outline" onClick={handleAnalyzeAgain} disabled={analyzing}>
                        {analyzing ? "Analyzing\u2026" : "Analyze again"}
                      </Button>
                      {analysisStatus === "draft" && (
                        <>
                          <Button variant="outline" onClick={handleRejectAnalysis} disabled={analyzing}>
                            Reject
                          </Button>
                          <Button onClick={handleApproveAnalysis} disabled={analyzing}>
                            Approve
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {resumeUnlocked ? (
          <Card aria-busy={tailoring}>
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0">
              <div className="flex flex-wrap items-center gap-3">
                <CardTitle className="text-lg">Tailored resume</CardTitle>
                <ReviewBadge status={resumeStatus} />
                <span className="text-sm text-muted-foreground">{resumeMeta.join(" · ")}</span>
              </div>
              <Button variant="outline" onClick={handleTailorAgain} disabled={tailoring}>
                {tailoring ? "Tailoring\u2026" : "Tailor again"}
              </Button>
            </CardHeader>
            <CardContent className={cn("flex flex-col gap-5 transition-opacity", tailoring && "opacity-50")}>
              {resumeStatus === "draft" && (
                <div role="alert" className="flex gap-3 rounded-md border border-amber-400 bg-amber-50 p-4 text-amber-900">
                  <TriangleAlert className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
                  <div className="flex flex-col gap-2 text-sm">
                    <p className="font-semibold">
                      {tailoredResume.flags.length} things in this draft are not in your base resume
                    </p>
                    <ul className="flex list-disc flex-col gap-1 pl-5">
                      {tailoredResume.flags.map((flag) => (
                        <li key={flag}>{flag}</li>
                      ))}
                    </ul>
                    <p>{tailoredResume.flagsNote}</p>
                  </div>
                </div>
              )}

              <div className="grid gap-6 lg:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <span id="base-resume-label" className="text-sm font-semibold">
                    Base resume (read-only)
                  </span>
                  <pre
                    aria-labelledby="base-resume-label"
                    className="min-h-96 flex-1 overflow-auto whitespace-pre-wrap rounded-md border bg-muted/40 p-4 font-mono text-sm leading-relaxed"
                  >
                    {tailoredResume.baseResume}
                  </pre>
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="resume-draft" className="font-semibold">
                    {resumeStatus === "draft" ? "Draft (you can edit this)" : "Draft"}
                  </Label>
                  <Textarea
                    id="resume-draft"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    readOnly={resumeStatus !== "draft"}
                    spellCheck={false}
                    className={cn(
                      "min-h-96 flex-1 p-4 font-mono text-sm leading-relaxed",
                      resumeStatus !== "draft" && "bg-muted/40",
                    )}
                  />
                </div>
              </div>

              <Separator />

              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-col gap-1 text-sm">
                  <span className="font-semibold">
                    Keyword coverage {tailoredResume.coverageChange.from}% {"\u2192"} {tailoredResume.coverageChange.to}%
                  </span>
                  <span className="text-muted-foreground">
                    {resumeStatus === "approved"
                      ? tailoredResume.approvedHint
                      : resumeStatus === "rejected"
                        ? tailoredResume.rejectedHint
                        : `Newly covered: ${tailoredResume.newlyCovered.join(", ")}. Still missing: ${tailoredResume.stillMissing.join(", ")}.`}
                  </span>
                </div>
                {resumeStatus === "draft" && (
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" disabled={tailoring}>
                      Save edits
                    </Button>
                    <Button variant="outline" onClick={handleRejectResume} disabled={tailoring}>
                      Reject
                    </Button>
                    <Button onClick={handleApproveResume} disabled={tailoring}>
                      Approve
                    </Button>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ) : (
          <section
            aria-labelledby="tailored-resume-locked"
            className="flex flex-col gap-4 rounded-xl border border-dashed bg-background p-6 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="flex gap-3">
              <Lock className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
              <div className="flex flex-col gap-1">
                <h2 id="tailored-resume-locked" className="text-lg font-semibold leading-none">
                  Tailored resume
                </h2>
                <p className="text-sm text-muted-foreground">{tailoredResume.lockedNote}</p>
              </div>
            </div>
            <Button variant="secondary" disabled>
              Tailor resume
            </Button>
          </section>
        )}

        <Card>
          <CardHeader className="flex flex-col gap-1 space-y-0">
            <CardTitle className="text-lg">{steps.applied.title}</CardTitle>
            <p className="text-sm text-muted-foreground">{markApplied.description}</p>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <fieldset className="flex flex-col gap-3" disabled={isApplied}>
              <legend className="mb-3 text-sm font-semibold">{markApplied.question}</legend>
              {resumeOptions.map((option) => (
                <ResumeOption
                  key={option.id}
                  id={option.id}
                  checked={sentResumeId === option.id}
                  onSelect={setSentResumeId}
                  label={option.label}
                >
                  {option.meta}
                </ResumeOption>
              ))}
            </fieldset>

            <Separator />

            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                {isApplied && sentResume
                  ? `Marked as applied today with your ${sentResume.label.toLowerCase()}.`
                  : markApplied.footnote}
              </p>
              <Button
                variant="outline"
                className="shrink-0"
                onClick={handleMarkApplied}
                disabled={isApplied || !sentResume}
              >
                {isApplied ? (
                  <>
                    <Check className="size-4" aria-hidden="true" />
                    Applied
                  </>
                ) : (
                  "Mark as applied"
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Timeline</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <form onSubmit={handleAddNote} className="flex flex-col gap-2">
              <Label htmlFor="timeline-note" className="font-normal text-muted-foreground">
                Add a note
              </Label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  id="timeline-note"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="For example: phone screen booked for Thursday"
                  className="flex-1"
                />
                <Button type="submit" variant="outline">
                  Add note
                </Button>
              </div>
            </form>

            <ol className="flex flex-col">
              {timeline.map((entry) => (
                <li key={entry.id} className="flex flex-col gap-1 border-t py-4 sm:flex-row sm:gap-8">
                  <span className="shrink-0 text-sm text-muted-foreground sm:w-28">{entry.date}</span>
                  <div className="flex flex-col gap-0.5 text-sm">
                    <span className="font-semibold">{entry.type}</span>
                    <span>{entry.text}</span>
                  </div>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}

function ReviewBadge({ status }: { status: ReviewStatus }) {
  if (status === "approved") {
    return (
      <Badge className="gap-1 border-transparent bg-green-100 text-green-800 hover:bg-green-100">
        <Check className="size-3" aria-hidden="true" />
        Approved
      </Badge>
    )
  }
  if (status === "rejected") {
    return (
      <Badge className="gap-1 border-transparent bg-red-100 text-red-800 hover:bg-red-100">
        <X className="size-3" aria-hidden="true" />
        Rejected
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="bg-muted">
      Draft
    </Badge>
  )
}

function ResumeOption({
  id,
  label,
  checked,
  onSelect,
  children,
}: {
  id: string
  label: string
  checked: boolean
  onSelect: (id: string) => void
  children: ReactNode
}) {
  const inputId = `sent-resume-${id}`
  return (
    <label
      htmlFor={inputId}
      className={cn(
        "flex cursor-pointer items-center gap-3 rounded-lg border p-4 transition-colors has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-70",
        checked ? "border-foreground" : "hover:bg-muted/40",
      )}
    >
      <input
        id={inputId}
        type="radio"
        name="sent-resume"
        value={id}
        checked={checked}
        onChange={() => onSelect(id)}
        className="size-4 shrink-0 accent-foreground"
      />
      <span className="flex flex-col">
        <span className="text-sm font-semibold">{label}</span>
        <span className="text-sm text-muted-foreground">{children}</span>
      </span>
    </label>
  )
}

function KeywordList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

function ChipGroup({ label, items, dashed = false }: { label: string; items: string[]; dashed?: boolean }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <ul className="flex flex-wrap gap-2" aria-label={`${label} keywords`}>
        {items.map((item) => (
          <li
            key={item}
            className={cn(
              "rounded-md border px-2.5 py-1 text-xs",
              dashed ? "border-dashed bg-background" : "bg-muted/60",
            )}
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}
