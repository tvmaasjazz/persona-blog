import { useParams } from 'react-router'

import { usePublicBlogPostCount } from '@/features/blog-posts/api/public-blog-post-count-query'
import { EditPersonaForm } from '@/features/personas/components/edit-persona-form'

export function EditPersonaPage() {
  const { personaIdentity } = useParams()

  if (!personaIdentity) {
    return null
  }

  return <LoadedEditPersonaPage personaIdentity={personaIdentity} />
}

type LoadedEditPersonaPageProps = {
  personaIdentity: string
}

// Split out so the count is read only with an identity.
function LoadedEditPersonaPage({ personaIdentity }: LoadedEditPersonaPageProps) {
  // The count feeds the warning before the persona goes private
  const { data: publicPostCount } = usePublicBlogPostCount(personaIdentity)

  return (
    <>
      <h1 className="mb-6 text-xl font-extrabold">Edit persona</h1>
      <EditPersonaForm personaIdentity={personaIdentity} publicPostCount={publicPostCount} />
    </>
  )
}
