import { createBrowserRouter } from 'react-router'

import { AppLayout, type AppRouteHandle } from '@/components/layout/app-layout'
import { RequireAuth } from '@/features/auth/components/require-auth'
import { BlogPostPage } from '@/routes/blog-post-page'
import { BlogPostsPage } from '@/routes/blog-posts-page'
import { EditBlogPostPage } from '@/routes/edit-blog-post-page'
import { EditPersonaPage } from '@/routes/edit-persona-page'
import { GenerateTextRunPage } from '@/routes/generate-text-run-page'
import { HomePage } from '@/routes/home-page'
import { NewPersonaPage } from '@/routes/new-persona-page'
import { PersonaPage } from '@/routes/persona-page'
import { PersonasPage } from '@/routes/personas-page'
import { WritePage } from '@/routes/write-page'

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
          {
            path: '/personas/:personaIdentity',
            element: <PersonaPage />,
            handle: { hasSidebar: true } satisfies AppRouteHandle,
          },
          { path: '/personas/:personaIdentity/edit', element: <EditPersonaPage /> },
          { path: '/write', element: <WritePage /> },
          { path: '/write/runs/:runIdentity', element: <GenerateTextRunPage /> },
          { path: '/posts', element: <BlogPostsPage /> },
          { path: '/posts/:blogPostIdentity', element: <BlogPostPage /> },
          { path: '/posts/:blogPostIdentity/edit', element: <EditBlogPostPage /> },
        ],
      },
    ],
  },
])
