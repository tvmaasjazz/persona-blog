import { useState } from 'react'
import { toast } from 'sonner'

import { MarkdownContent } from '@/components/markdown-content'
import { Button } from '@/components/ui/button'
import { useResumeGenerateText } from '@/features/generate-text/api/use-resume-generate-text'
import { RequestChangesForm } from '@/features/generate-text/components/request-changes-form'

type RunReviewProps = {
  runIdentity: string
  lastStep: string | null
  content: string
}

const REVIEW_STEP_NAMES: Record<string, string> = {
  REVIEW_OUTLINE: 'Outline',
  REVIEW_DRAFT: 'Draft',
  REVIEW_HUMANIZE: 'Humanize',
}

export function RunReview({ runIdentity, lastStep, content }: RunReviewProps) {
  const resumeGenerateText = useResumeGenerateText()
  const [isRequestingChanges, setIsRequestingChanges] = useState(false)
  const stepName = (lastStep && REVIEW_STEP_NAMES[lastStep]) || 'Review'
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
    <section className="flex flex-col gap-4 rounded-2xl border bg-card p-6">
      <h2 className="text-xl font-extrabold">{stepName} ready for review</h2>
      <MarkdownContent markdown={content} />
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
      {isWorking && (
        <p className="text-sm text-muted-foreground">Working… this can take a minute or more.</p>
      )}
    </section>
  )
}
