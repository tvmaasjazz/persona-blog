import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { useGenerateTextRun } from '@/features/generate-text/api/generate-text-run-query'
import type { PersonaChoice } from '@/features/generate-text/components/generate-blog-post-form'
import { WriteBlogPostForm } from '@/features/generate-text/components/write-blog-post-form'
import {
  EMPTY_GENERATE_BLOG_POST_FORM_VALUES,
  toFormValuesFromRun,
} from '@/features/generate-text/generate-blog-post-form-schema'

type WriteBlogPostProps = {
  personas: PersonaChoice[]
  preselectedPersonaIdentity: string | null
  fromRunIdentity: string | null
}

type RunPrefillProps = {
  personas: PersonaChoice[]
  fromRunIdentity: string
}

function RunPrefill({ personas, fromRunIdentity }: RunPrefillProps) {
  // Load the run to copy
  const { data: run, isPending, error } = useGenerateTextRun(fromRunIdentity)

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  if (error) {
    return <p className="text-muted-foreground">Couldn't load that run to copy from.</p>
  }

  // Prefill the form from the run
  const isPersonaKnown = personas.some((persona) => persona.identity === run.persona_identity)
  return (
    <WriteBlogPostForm
      personas={personas}
      initialValues={toFormValuesFromRun(run, isPersonaKnown ? (run.persona_identity ?? '') : '')}
    />
  )
}

export function WriteBlogPost({
  personas,
  preselectedPersonaIdentity,
  fromRunIdentity,
}: WriteBlogPostProps) {
  // No personas: ask for one first
  if (personas.length === 0) {
    return (
      <div className="flex flex-col items-start gap-4">
        <p className="text-muted-foreground">Create a persona before writing a post.</p>
        <Button asChild>
          <Link to="/personas/new">Create a persona</Link>
        </Button>
      </div>
    )
  }

  // Copying a run
  if (fromRunIdentity) {
    return (
      <RunPrefill key={fromRunIdentity} personas={personas} fromRunIdentity={fromRunIdentity} />
    )
  }

  // Blank form with the preselected persona's defaults
  const persona = personas.find((choice) => choice.identity === preselectedPersonaIdentity)
  return (
    // Keyed so a different ?persona= link resets the defaults
    <WriteBlogPostForm
      key={preselectedPersonaIdentity ?? ''}
      personas={personas}
      initialValues={{
        ...EMPTY_GENERATE_BLOG_POST_FORM_VALUES,
        persona_identity: persona?.identity ?? '',
        tone: persona?.default_tone ?? '',
        target_audience: persona?.default_target_audience ?? '',
      }}
    />
  )
}
