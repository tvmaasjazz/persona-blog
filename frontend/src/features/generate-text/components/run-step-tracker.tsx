import { Check } from 'lucide-react'

import { findRunStepName, listSteps } from '@/features/generate-text/run-steps'
import type { components } from '@/lib/api-schema.gen'
import { cn } from '@/lib/utils'

type GenerateTextRunResponseDto = components['schemas']['GenerateTextRunResponseDto']

type RunStepTrackerProps = {
  run: GenerateTextRunResponseDto
}

// Outline → Draft → Humanize → Save, with the run's current step marked.
export function RunStepTracker({ run }: RunStepTrackerProps) {
  // Steps to show, and where the run is
  const stepNames = [
    ...listSteps({
      isOutlineEnabled: run.options.outline?.is_enabled ?? false,
      isHumanizeEnabled: run.options.humanize?.is_enabled ?? false,
    }),
    'Save',
  ]
  const currentStepName = run.status === 'COMPLETED' ? 'Save' : findRunStepName(run.last_step)
  const currentStepIndex = currentStepName ? stepNames.indexOf(currentStepName) : 0

  // One marked item per step
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      {stepNames.map((stepName, stepIndex) => {
        const isDone = stepIndex < currentStepIndex
        const isCurrent = stepIndex === currentStepIndex

        return (
          <li key={stepName} className="flex items-center gap-2">
            {stepIndex > 0 && <span className="text-muted-foreground">→</span>}
            <span
              className={cn(
                'flex items-center gap-1 rounded-lg px-2 py-1',
                isCurrent ? 'bg-accent font-semibold' : 'text-muted-foreground',
              )}
              aria-current={isCurrent ? 'step' : undefined}
            >
              {isDone && <Check aria-hidden className="size-4" />}
              {stepName}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
