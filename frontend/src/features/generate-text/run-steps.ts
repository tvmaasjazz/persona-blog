import type { components } from '@/lib/api-schema.gen'

type GenerateTextRunResponseDto = components['schemas']['GenerateTextRunResponseDto']

type DescribeStepsInput = {
  isOutlineEnabled: boolean
  isHumanizeEnabled: boolean
}

// last_step holds the review node a paused run is waiting in.
const REVIEW_STEP_NAMES: Record<string, string> = {
  REVIEW_OUTLINE: 'Outline',
  REVIEW_DRAFT: 'Draft',
  REVIEW_HUMANIZE: 'Humanized draft',
}

export function findReviewStepName(lastStep: string | null): string {
  return (lastStep && REVIEW_STEP_NAMES[lastStep]) || 'Step'
}

export function describeSteps({ isOutlineEnabled, isHumanizeEnabled }: DescribeStepsInput): string {
  const stepNames = []
  if (isOutlineEnabled) {
    stepNames.push('Outline')
  }
  stepNames.push('Draft')
  if (isHumanizeEnabled) {
    stepNames.push('Humanize')
  }
  return stepNames.join(', ')
}

// What a toast says when a generate or resume call comes back, or null when the run
// has nothing new to look at.
export function describeRunReady(run: GenerateTextRunResponseDto): string | null {
  if (run.status === 'AWAITING_REVIEW') {
    return `${findReviewStepName(run.last_step)} ready for review`
  }
  if (run.status === 'COMPLETED') {
    return 'Your post is ready'
  }
  return null
}
