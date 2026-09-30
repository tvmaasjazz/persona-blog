import { createBrowserRouter } from 'react-router'

import { AppLayout } from '@/components/layout/app-layout'
import { RequireAuth } from '@/features/auth/components/require-auth'
import { EditPersonaPage } from '@/routes/edit-persona-page'
import { HomePage } from '@/routes/home-page'
import { NewPersonaPage } from '@/routes/new-persona-page'
import { PersonaPage } from '@/routes/persona-page'
import { PersonasPage } from '@/routes/personas-page'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      {
        element: <RequireAuth />,
        children: [
          { path: '/personas', element: <PersonasPage /> },
          { path: '/personas/new', element: <NewPersonaPage /> },
          { path: '/personas/:personaIdentity', element: <PersonaPage /> },
          { path: '/personas/:personaIdentity/edit', element: <EditPersonaPage /> },
        ],
      },
    ],
  },
])
