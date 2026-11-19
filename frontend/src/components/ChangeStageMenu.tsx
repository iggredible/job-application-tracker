import { ChevronDown } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useChangeStage } from '@/hooks/useApplications'
import { stageLabel, type Application, type Stage } from '@/lib/applications'

/** Lists only the stages the API says this application may move to. */
export function ChangeStageMenu({ application }: { application: Application }) {
  const changeStage = useChangeStage(application.id)
  const options = application.allowed_next_stages

  function choose(stage: Stage) {
    changeStage.mutate(stage, {
      onSuccess: () => toast.success(`Moved to ${stageLabel(stage)}`),
      onError: (error) => toast.error(error.message || 'Could not change the stage'),
    })
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" disabled={options.length === 0 || changeStage.isPending}>
          Change stage
          <ChevronDown aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {options.map((stage) => (
          <DropdownMenuItem key={stage} onSelect={() => choose(stage)}>
            {stageLabel(stage)}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
