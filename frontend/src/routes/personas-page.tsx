import { Plus } from 'lucide-react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { PersonaList } from '@/features/personas/components/persona-list'

export function PersonasPage() {
  return (
    <>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-extrabold">My Personas</h1>
        <Button asChild>
          <Link to="/personas/new">
            <Plus aria-hidden />
            New persona
          </Link>
        </Button>
      </div>
      <PersonaList />
    </>
  )
}
