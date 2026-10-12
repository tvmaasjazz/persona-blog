import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { MarkdownContent } from '@/components/markdown-content'
import { Button } from '@/components/ui/button'
import { RunInputsSummary } from '@/features/generate-text/components/run-inputs-summary'
import { RunReview } from '@/features/generate-text/components/run-review'
import { describeSteps } from '@/features/generate-text/run-steps'
import type { components } from '@/lib/api-schema.gen'

type GenerateTextRunResponseDto = components['schemas']['GenerateTextRunResponseDto']

type GenerateTextRunViewProps = {
  run: GenerateTextRunResponseDto
  personaName: string | null
  completedActions: ReactNode
}

function RunStatus({
  run,
  completedActions,
}: Pick<GenerateTextRunViewProps, 'run' | 'completedActions'>) {
  switch (run.status) {
    case 'AWAITING_REVIEW':
      return (
        // Keyed per LLM call, so each new step starts with Request changes closed.
        <RunReview
          key={run.llm_call_count}
          runIdentity={run.run_identity}
          lastStep={run.last_step}
          content={run.content}
        />
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
    <div className="flex flex-col gap-6">
      <RunInputsSummary
        title="What you asked for"
        personaName={personaName ?? 'Persona no longer available'}
        promptText={run.prompt_text}
        tone={run.tone}
        targetAudience={run.target_audience}
        additionalContext={run.additional_context}
        stepsLabel={describeSteps({
          isOutlineEnabled: run.options.outline?.is_enabled ?? false,
          isHumanizeEnabled: run.options.humanize?.is_enabled ?? false,
        })}
      />
      <RunStatus run={run} completedActions={completedActions} />
      <footer className="text-sm text-muted-foreground">
        {run.llm_call_count} LLM calls · {run.input_tokens + run.output_tokens} tokens · $
        {run.cost_usd}
      </footer>
    </div>
  )
}
