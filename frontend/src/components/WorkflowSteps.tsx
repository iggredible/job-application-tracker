import { Check } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { StepKey, WorkflowStep } from '@/lib/applications'

// Display names only. The API decides each step's status and the line under the name.
const NAMES: Record<StepKey, string> = {
  analysis: 'Posting analysis',
  tailored: 'Tailored resume',
  apply: 'Mark as applied',
}

/** The three steps under the header. It draws what the API sends and works nothing out: a check
 * for done, a highlighted border for current, a dashed border for the rest. */
export function WorkflowSteps({ steps }: { steps: WorkflowStep[] }) {
  return (
    <ol aria-label="Workflow steps" className="grid gap-3 md:grid-cols-3">
      {steps.map((step, index) => (
        <li
          key={step.key}
          data-status={step.status}
          className={cn(
            'flex items-center gap-3 rounded-lg border bg-card px-4 py-3',
            step.status === 'current' && 'border-2 border-foreground',
            ['locked', 'available', 'skipped'].includes(step.status) && 'border-dashed',
          )}
        >
          {step.status === 'done' ? (
            <span
              data-testid="step-check"
              className="flex size-7 shrink-0 items-center justify-center rounded-full bg-emerald-800 text-white"
            >
              <Check className="size-4" aria-hidden="true" />
            </span>
          ) : (
            <span
              aria-hidden="true"
              className={cn(
                'flex size-7 shrink-0 items-center justify-center rounded-full border text-sm',
                step.status === 'current' && 'border-foreground bg-foreground text-background',
              )}
            >
              {index + 1}
            </span>
          )}
          <div className="min-w-0">
            <p className="text-sm font-semibold">{`${index + 1}. ${NAMES[step.key]}`}</p>
            <p className="text-sm text-muted-foreground">{step.text}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
