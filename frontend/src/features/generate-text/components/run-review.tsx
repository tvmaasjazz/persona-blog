import { useState } from 'react'
import { toast } from 'sonner'

import { MarkdownContent } from '@/components/markdown-content'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useResumeGenerateText } from '@/features/generate-text/api/use-resume-generate-text'

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
  const [feedbackText, setFeedbackText] = useState('')
  const stepName = (lastStep && REVIEW_STEP_NAMES[lastStep]) || 'Review'
  const isWorking = resumeGenerateText.isPending
  const trimmedFeedback = feedbackText.trim()

  function resume(isApproved: boolean) {
    resumeGenerateText.mutate(
      {
        runIdentity,
        resume: { is_approved: isApproved, feedback_text: isApproved ? null : trimmedFeedback },
      },
      { onError: () => toast.error("Couldn't continue the run. Try again.") },
    )
  }

  return (
    <section className="flex flex-col gap-4 rounded-2xl border bg-card p-6">
      <h2 className="text-xl font-extrabold">{stepName} ready for review</h2>
      <MarkdownContent markdown={content} />
      <div className="flex flex-wrap gap-3">
        <Button disabled={isWorking} onClick={() => resume(true)}>
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
        <div className="flex flex-col gap-3">
          <Label htmlFor="run-feedback">What should change?</Label>
          <Textarea
            id="run-feedback"
            rows={4}
            value={feedbackText}
            onChange={(event) => setFeedbackText(event.target.value)}
          />
          <div className="flex gap-3">
            <Button
              variant="secondary"
              disabled={isWorking || trimmedFeedback === ''}
              onClick={() => resume(false)}
            >
              Send
            </Button>
            <Button
              variant="ghost"
              disabled={isWorking}
              onClick={() => setIsRequestingChanges(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
      {isWorking && (
        <p className="text-sm text-muted-foreground">Working… this can take a minute or more.</p>
      )}
    </section>
  )
}
