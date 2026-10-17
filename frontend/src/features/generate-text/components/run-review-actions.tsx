import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { useResumeGenerateText } from '@/features/generate-text/api/use-resume-generate-text'
import { RequestChangesForm } from '@/features/generate-text/components/request-changes-form'
import { findReviewStepName } from '@/features/generate-text/run-steps'

type RunReviewActionsProps = {
  runIdentity: string
  lastStep: string | null
}

// Approve or request changes for the step a run is paused on. The step's text is in
// the main column; these sit in the sidebar so they're always in view.
export function RunReviewActions({ runIdentity, lastStep }: RunReviewActionsProps) {
  const resumeGenerateText = useResumeGenerateText()
  const [isRequestingChanges, setIsRequestingChanges] = useState(false)
  const stepName = findReviewStepName(lastStep)
  const isWorking = resumeGenerateText.isPending

  async function resume(isApproved: boolean, feedbackText: string | null) {
    if (isWorking) {
      return
    }
    try {
      await resumeGenerateText.mutateAsync({
        runIdentity,
        resume: { is_approved: isApproved, feedback_text: feedbackText },
      })
    } catch {
      toast.error("Couldn't continue the run. Try again.")
    }
  }

  return (
    <section className="flex flex-col gap-4 rounded-2xl border bg-card p-5">
      <div className="flex flex-col gap-1">
        <h2 className="font-bold">Review the {stepName.toLowerCase()}</h2>
        <p className="text-sm text-muted-foreground">
          Approve it to move on, or say what should change.
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button disabled={isWorking} onClick={() => void resume(true, null)}>
          Approve
        </Button>
        {!isRequestingChanges && (
          <Button
            variant="secondary"
            disabled={isWorking}
            onClick={() => setIsRequestingChanges(true)}
          >
            Request changes
          </Button>
        )}
      </div>
      {isRequestingChanges && (
        <RequestChangesForm
          isDisabled={isWorking}
          onSend={(feedbackText) => resume(false, feedbackText)}
          onCancel={() => setIsRequestingChanges(false)}
        />
      )}
    </section>
  )
}
