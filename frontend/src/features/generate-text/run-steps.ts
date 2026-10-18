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

export type RunStepName = 'Outline' | 'Draft' | 'Humanize'

export function listSteps({
  isOutlineEnabled,
  isHumanizeEnabled,
}: DescribeStepsInput): RunStepName[] {
  const stepNames: RunStepName[] = []
  if (isOutlineEnabled) {
    stepNames.push('Outline')
  }
  stepNames.push('Draft')
  if (isHumanizeEnabled) {
    stepNames.push('Humanize')
  }
  return stepNames
}

export function describeSteps(describeStepsInput: DescribeStepsInput): string {
  return listSteps(describeStepsInput).join(', ')
}

// The step a run's last node belongs to: REVIEW_DRAFT and REWRITE_DRAFT are both Draft.
export function findRunStepName(lastStep: string | null): RunStepName | null {
  if (lastStep?.includes('OUTLINE')) {
    return 'Outline'
  }
  if (lastStep?.includes('DRAFT')) {
    return 'Draft'
  }
  if (lastStep?.includes('HUMANIZE')) {
    return 'Humanize'
  }
  return null
}

// The toast text for a run that needs attention, or null.
export function describeRunReady(run: GenerateTextRunResponseDto): string | null {
  if (run.status === 'AWAITING_REVIEW') {
    return `${findReviewStepName(run.last_step)} ready for review`
  }
  if (run.status === 'COMPLETED') {
    return 'Your post is ready'
  }
  return null
}
