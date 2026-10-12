import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { MarkdownContent } from '@/components/markdown-content'
import { Button } from '@/components/ui/button'
import { RunReview } from '@/features/generate-text/components/run-review'
import type { components } from '@/lib/api-schema.gen'

type GenerateTextRunResponseDto = components['schemas']['GenerateTextRunResponseDto']

type GenerateTextRunViewProps = {
  run: GenerateTextRunResponseDto
  personaName: string | null
  completedActions: ReactNode
}

type SummaryRowProps = {
  label: string
  value: string | null
}

function SummaryRow({ label, value }: SummaryRowProps) {
  if (!value) {
    return null
  }
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-sm font-semibold">{label}</dt>
      <dd className="whitespace-pre-wrap text-muted-foreground">{value}</dd>
    </div>
  )
}

function describeSteps(options: GenerateTextRunResponseDto['options']): string {
  const steps = []
  if (options.outline?.is_enabled) {
    steps.push('Outline')
  }
  steps.push('Draft')
  if (options.humanize?.is_enabled) {
    steps.push('Humanize')
  }
  return steps.join(', ')
}

function RunStatus({
  run,
  completedActions,
}: Pick<GenerateTextRunViewProps, 'run' | 'completedActions'>) {
  switch (run.status) {
    case 'AWAITING_REVIEW':
      return (
        <RunReview runIdentity={run.run_identity} lastStep={run.last_step} content={run.content} />
      )
    case 'COMPLETED':
      return (
        <div className="flex flex-col gap-8">
          <MarkdownContent markdown={run.content} />
          <section className="flex flex-col gap-4 rounded-2xl border bg-card p-6">
            <h2 className="text-xl font-extrabold">Save as a post</h2>
            {completedActions}
          </section>
        </div>
      )
    case 'FAILED':
      return (
        <div className="flex flex-col items-start gap-4">
          <p className="text-muted-foreground">Something went wrong while writing this post.</p>
          <Button asChild>
            <Link to={`/write?from_run=${run.run_identity}`}>Try again</Link>
          </Button>
        </div>
      )
    case 'CANCELLED':
      return (
        <div className="flex flex-col items-start gap-4">
          <p className="text-muted-foreground">This run was cancelled.</p>
          <Button asChild variant="secondary">
            <Link to="/write">Write a new post</Link>
          </Button>
        </div>
      )
    default:
      return (
        <p className="text-muted-foreground" role="status">
          Writing… this can take a minute or more.
        </p>
      )
  }
}

export function GenerateTextRunView({
  run,
  personaName,
  completedActions,
}: GenerateTextRunViewProps) {
  return (
    <div className="flex flex-col gap-8">
      <RunStatus run={run} completedActions={completedActions} />
      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-bold">What you asked for</h2>
        <dl className="flex flex-col gap-3">
          <SummaryRow label="Persona" value={personaName ?? 'Persona no longer available'} />
          <SummaryRow label="Prompt" value={run.prompt_text} />
          <SummaryRow label="Tone" value={run.tone} />
          <SummaryRow label="Target audience" value={run.target_audience} />
          <SummaryRow label="Additional context" value={run.additional_context} />
          <SummaryRow label="Steps" value={describeSteps(run.options)} />
        </dl>
      </section>
      <footer className="text-sm text-muted-foreground">
        {run.llm_call_count} LLM calls · {run.input_tokens + run.output_tokens} tokens · $
        {run.cost_usd}
      </footer>
    </div>
  )
}
