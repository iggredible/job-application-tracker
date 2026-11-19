import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useResume, useSaveResume } from '@/hooks/useResume'
import { formatDateTime } from '@/lib/applications'

// Static guidance. Not data, so it lives with the page.
const HOW_THIS_IS_USED = [
  'Tailoring only rephrases, reorders and emphasizes what is written here. It never adds new facts.',
  'Every tailored draft is checked against this text. Employers, titles, dates, numbers and skills that are not here get flagged.',
  'If a posting shows a missing keyword you really have, add it here, then tailor again.',
  'Include everything you can honestly claim. Length does not matter; each tailored resume is a selection.',
]

export function ResumePage() {
  const { data: resume, isPending, isError } = useResume()
  const save = useSaveResume()
  // What the user has typed since the last save. null means the editor shows the saved text.
  const [draft, setDraft] = useState<string | null>(null)

  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>
  // Without the saved text the editor could overwrite it, so it is not shown.
  if (isError) return <p className="text-sm text-muted-foreground">Could not load the resume.</p>

  const text = draft ?? resume?.content_markdown ?? ''

  function handleSave() {
    save.mutate(text, {
      onSuccess: () => {
        setDraft(null)
        toast.success('Resume saved')
      },
      onError: (error) => toast.error(error.message || 'Could not save the resume'),
    })
  }

  return (
    <div className="grid gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Base resume</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Every tailored resume is written from this document.
          </p>
        </div>
        <div className="flex items-center gap-4">
          {resume && (
            <span className="text-sm text-muted-foreground">
              Last saved {formatDateTime(resume.updated_at)}
            </span>
          )}
          <Button onClick={handleSave} disabled={text.trim() === '' || save.isPending}>
            Save
          </Button>
        </div>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Card>
          <CardContent className="grid gap-2">
            <Label htmlFor="resume-markdown">Resume in Markdown</Label>
            <Textarea
              id="resume-markdown"
              value={text}
              onChange={(e) => setDraft(e.target.value)}
              spellCheck={false}
              className="min-h-[38rem] resize-y font-mono"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>How this is used</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="grid list-disc gap-3 pl-5 text-sm">
              {HOW_THIS_IS_USED.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
