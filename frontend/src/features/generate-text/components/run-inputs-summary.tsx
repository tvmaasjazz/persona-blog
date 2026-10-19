import { ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

type RunInputsSummaryProps = {
  title: string
  status?: ReactNode
  personaName: string
  promptText: string
  tone: string | null
  targetAudience: string | null
  additionalContext: string | null
  stepsLabel: string
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

// The run's inputs, folded behind Show details.
export function RunInputsSummary({
  title,
  status,
  personaName,
  promptText,
  tone,
  targetAudience,
  additionalContext,
  stepsLabel,
}: RunInputsSummaryProps) {
  return (
    <Collapsible className="flex flex-col gap-3 rounded-2xl border bg-card p-5">
      <div className="flex min-w-0 flex-col gap-1">
        <h2 className="font-bold">{title}</h2>
        <p className="text-sm text-muted-foreground">{personaName}</p>
      </div>
      {status}
      <p className="line-clamp-2 whitespace-pre-wrap">{promptText}</p>
      <CollapsibleTrigger asChild>
        <Button variant="link" className="group h-auto self-start px-0">
          <span className="group-data-[state=open]:hidden">Show details</span>
          <span className="hidden group-data-[state=open]:inline">Hide details</span>
          <ChevronDown
            aria-hidden
            className="transition-transform group-data-[state=open]:rotate-180"
          />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <dl className="flex flex-col gap-3 border-t pt-3">
          <SummaryRow label="Prompt" value={promptText} />
          <SummaryRow label="Tone" value={tone} />
          <SummaryRow label="Target audience" value={targetAudience} />
          <SummaryRow label="Additional context" value={additionalContext} />
          <SummaryRow label="Steps" value={stepsLabel} />
        </dl>
      </CollapsibleContent>
    </Collapsible>
  )
}
