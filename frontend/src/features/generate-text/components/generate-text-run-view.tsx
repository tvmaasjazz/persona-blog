import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import { toast } from 'sonner'

import { PageWithSidebar } from '@/components/layout/page-with-sidebar'
import { MarkdownContent } from '@/components/markdown-content'
import { Button } from '@/components/ui/button'
import { DiscardRunButton } from '@/features/generate-text/components/discard-run-button'
import { LeaveUnsavedRunDialog } from '@/features/generate-text/components/leave-unsaved-run-dialog'
import { RunInputsSummary } from '@/features/generate-text/components/run-inputs-summary'
import { RunReviewActions } from '@/features/generate-text/components/run-review-actions'
import { RunStepTracker } from '@/features/generate-text/components/run-step-tracker'
import { useUnsavedRunGuard } from '@/features/generate-text/hooks/use-unsaved-run-guard'
import { describeSteps, findReviewStepName } from '@/features/generate-text/run-steps'
import type { components } from '@/lib/api-schema.gen'

type GenerateTextRunResponseDto = components['schemas']['GenerateTextRunResponseDto']

type CompletedActionsInput = {
  // Lets the page leave without the unsaved-post prompt once the post is saved.
  onSaved: () => void
  discardButton: ReactNode
}

type GenerateTextRunViewProps = {
  run: GenerateTextRunResponseDto
  personaName: string | null
  // The save form, which the route composes from the blog-posts feature.
  renderCompletedActions: (completedActionsInput: CompletedActionsInput) => ReactNode
}

type RunPartProps = {
  run: GenerateTextRunResponseDto
}

// The text the run is on: the step to review, or the finished post.
function RunContent({ run }: RunPartProps) {
  switch (run.status) {
    case 'AWAITING_REVIEW':
      return (
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-muted-foreground">
            {findReviewStepName(run.last_step)} ready for review
          </h2>
          <MarkdownContent markdown={run.content} />
        </div>
      )
    case 'COMPLETED':
      return <MarkdownContent markdown={run.content} />
    case 'FAILED':
      return <p className="text-muted-foreground">Something went wrong while writing this post.</p>
    case 'CANCELLED':
      return <p className="text-muted-foreground">This run was cancelled.</p>
    default:
      return (
        <p className="text-muted-foreground" role="status">
          Writing… this can take a minute or more.
        </p>
      )
  }
}

type RunActionsProps = RunPartProps & {
  completedActions: ReactNode
}

// What you can do next, in the sidebar so it's always in view.
function RunActions({ run, completedActions }: RunActionsProps) {
  switch (run.status) {
    case 'AWAITING_REVIEW':
      // Keyed per LLM call, so each new step starts with Request changes closed.
      return (
        <RunReviewActions
          key={run.llm_call_count}
          runIdentity={run.run_identity}
          lastStep={run.last_step}
        />
      )
    case 'COMPLETED':
      return (
        <section className="flex flex-col gap-4 rounded-2xl border bg-card p-5">
          <h2 className="font-bold">Save as a post</h2>
          {completedActions}
        </section>
      )
    case 'FAILED':
      return (
        <Button asChild>
          <Link to={`/write?from_run=${run.run_identity}`}>Try again</Link>
        </Button>
      )
    case 'CANCELLED':
      return (
        <Button asChild variant="secondary">
          <Link to="/write">Write a new post</Link>
        </Button>
      )
    default:
      return null
  }
}

export function GenerateTextRunView({
  run,
  personaName,
  renderCompletedActions,
}: GenerateTextRunViewProps) {
  const navigate = useNavigate()
  const { blocker, allowLeave } = useUnsavedRunGuard(run.status === 'COMPLETED')

  function discardRun() {
    allowLeave()
    toast.success('Post discarded')
    navigate('/write')
  }

  return (
    <>
      <PageWithSidebar
        header={
          <header className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <h1 className="text-xl font-extrabold">Writing a post</h1>
              <p className="text-muted-foreground">
                as {personaName ?? 'a persona that is no longer available'}
              </p>
            </div>
            <RunStepTracker run={run} />
          </header>
        }
        sidebar={
          <>
            <RunActions
              run={run}
              completedActions={renderCompletedActions({
                onSaved: allowLeave,
                discardButton: <DiscardRunButton onDiscard={discardRun} />,
              })}
            />
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
            <p className="text-sm text-muted-foreground">
              {run.llm_call_count} LLM calls · {run.input_tokens + run.output_tokens} tokens · $
              {run.cost_usd}
            </p>
          </>
        }
      >
        <RunContent run={run} />
      </PageWithSidebar>
      <LeaveUnsavedRunDialog blocker={blocker} />
    </>
  )
}
