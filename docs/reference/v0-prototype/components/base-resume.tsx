import { useState } from "react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

export const baseResumeData = {
  app: {
    name: "Job Tracker",
    nav: [
      { label: "Applications", href: "#", active: false },
      { label: "Resume", href: "#", active: true },
      { label: "Insights", href: "#", active: false },
    ],
  },
  page: {
    title: "Base resume",
    description: "Every tailored resume is written from this document.",
    editorLabel: "Resume in Markdown",
  },
  lastSaved: "Nov 12, 4:20 PM",
  resume: `# Jordan Avery
Lead Software Engineer · Austin, TX

## Experience
### Lead Software Engineer — Coldline Logistics (Jun 2021 — May 2026)
- Led a team of 5 building shipment tracking and order management in Rails
- Built NetSuite integrations between internal systems
- Moved slow reports to background jobs with Sidekiq
- Maintained CI pipelines and code review standards

### Software Engineer — Harbor Mortgage (2018 — 2021)
- Built REST APIs on Rails and PostgreSQL for loan servicing

## Skills
Ruby on Rails, PostgreSQL, Sidekiq, REST APIs, NetSuite, RSpec`,
  guidance: {
    title: "How this is used",
    points: [
      "Tailoring only rephrases, reorders and emphasizes what is written here. It never adds new facts.",
      "Every tailored draft is checked against this text. Employers, titles, dates, numbers and skills that are not here get flagged.",
      "If a posting shows a missing keyword you really have, add it here, then tailor again.",
      "Include everything you can honestly claim. Length does not matter; each tailored resume is a selection.",
    ],
  },
}

type BaseResumeData = typeof baseResumeData

function formatNow() {
  const now = new Date()
  const date = now.toLocaleDateString("en-US", { month: "short", day: "numeric" })
  const time = now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
  return `${date}, ${time}`
}

export default function BaseResume({
  data = baseResumeData,
  onNavigate,
  onSave,
}: {
  data?: BaseResumeData
  onNavigate?: (label: string) => void
  onSave?: (resume: string) => void
}) {
  const { app, page, guidance } = data
  const [resume, setResume] = useState(data.resume)
  const [savedResume, setSavedResume] = useState(data.resume)
  const [lastSaved, setLastSaved] = useState(data.lastSaved)
  const hasChanges = resume !== savedResume

  function handleSave() {
    onSave?.(resume)
    setSavedResume(resume)
    setLastSaved(formatNow())
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

      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{page.title}</h1>
            <p className="text-sm text-muted-foreground">{page.description}</p>
          </div>
          <div className="flex items-center gap-4">
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {hasChanges ? "Unsaved changes" : `Last saved ${lastSaved}`}
            </p>
            <Button size="lg" onClick={handleSave}>
              Save
            </Button>
          </div>
        </div>

        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <Card className="gap-0 py-5">
            <CardContent className="flex flex-col gap-3 px-5">
              <Label htmlFor="base-resume">{page.editorLabel}</Label>
              <Textarea
                id="base-resume"
                value={resume}
                onChange={(event) => setResume(event.target.value)}
                spellCheck={false}
                className="min-h-[38rem] resize-y bg-background p-4 font-mono text-sm leading-relaxed"
              />
            </CardContent>
          </Card>

          <Card className="gap-4 py-5">
            <CardHeader className="px-5">
              <CardTitle className="text-base">{guidance.title}</CardTitle>
            </CardHeader>
            <CardContent className="px-5">
              <ul className="flex list-disc flex-col gap-3 pl-4 text-sm leading-relaxed text-muted-foreground marker:text-foreground">
                {guidance.points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}
