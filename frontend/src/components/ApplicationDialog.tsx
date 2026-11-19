import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { useCreateApplication, useUpdateApplication } from '@/hooks/useApplications'
import { SOURCES, type Application, type Source } from '@/lib/applications'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Pass an application to edit it. Without one the dialog creates a new application. */
  application?: Application
  onSaved?: (application: Application) => void
}

/** One dialog for both creating and editing an application. */
export function ApplicationDialog({ open, onOpenChange, application, onSaved }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        {/* Mounted only while open, so the fields start fresh every time. */}
        <ApplicationForm
          application={application}
          onClose={() => onOpenChange(false)}
          onSaved={onSaved}
        />
      </DialogContent>
    </Dialog>
  )
}

function ApplicationForm({
  application,
  onClose,
  onSaved,
}: {
  application?: Application
  onClose: () => void
  onSaved?: (application: Application) => void
}) {
  const editing = application !== undefined
  const [company, setCompany] = useState(application?.company ?? '')
  const [role, setRole] = useState(application?.role ?? '')
  const [source, setSource] = useState<Source | ''>(application?.source ?? '')
  const [postingUrl, setPostingUrl] = useState(application?.posting_url ?? '')
  const [postingText, setPostingText] = useState(application?.posting_text ?? '')

  const create = useCreateApplication()
  const update = useUpdateApplication(application?.id ?? 0)
  const mutation = editing ? update : create

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (source === '') return
    mutation.mutate(
      {
        company,
        role,
        source,
        posting_url: postingUrl.trim() === '' ? null : postingUrl.trim(),
        posting_text: postingText,
      },
      {
        onSuccess: (saved) => {
          toast.success(editing ? 'Application updated' : 'Application saved')
          onClose()
          onSaved?.(saved)
        },
        onError: (error) => toast.error(error.message || 'Could not save the application'),
      },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{editing ? 'Edit application' : 'New application'}</DialogTitle>
        <DialogDescription>
          {editing ? 'Change the details of this application.' : 'It will be saved in the Saved stage.'}
        </DialogDescription>
      </DialogHeader>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="app-company">Company</Label>
          <Input
            id="app-company"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            required
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="app-role">Role</Label>
          <Input id="app-role" value={role} onChange={(e) => setRole(e.target.value)} required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="app-source">Source</Label>
          <NativeSelect
            id="app-source"
            className="w-full"
            value={source}
            onChange={(e) => setSource(e.target.value as Source | '')}
            required
          >
            <NativeSelectOption value="">Select a source</NativeSelectOption>
            {SOURCES.map((s) => (
              <NativeSelectOption key={s.value} value={s.value}>
                {s.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="app-url">
            Posting URL <span className="font-normal text-muted-foreground">(optional)</span>
          </Label>
          <Input
            id="app-url"
            type="url"
            value={postingUrl}
            onChange={(e) => setPostingUrl(e.target.value)}
          />
        </div>
      </div>

      <div className="grid gap-2">
        <Label htmlFor="app-text">Posting text</Label>
        <Textarea
          id="app-text"
          className="max-h-[50vh] min-h-48 overflow-y-auto"
          value={postingText}
          onChange={(e) => setPostingText(e.target.value)}
          required
        />
        <p className="text-xs text-muted-foreground">
          Paste the full job description. The app does not fetch it from the URL.
        </p>
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {editing ? 'Save changes' : 'Save application'}
        </Button>
      </DialogFooter>
    </form>
  )
}
