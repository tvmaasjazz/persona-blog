import { createBrowserRouter } from 'react-router'

import { AppLayout, type AppRouteHandle } from '@/components/layout/app-layout'
import { RequireAuth } from '@/features/auth/components/require-auth'
import { RequirePermission } from '@/features/auth/components/require-permission'
import { AccountPage } from '@/routes/account-page'
import { AdminUserPage } from '@/routes/admin-user-page'
import { AdminUsersPage } from '@/routes/admin-users-page'
import { BlogPostPage } from '@/routes/blog-post-page'
import { BlogPostsPage } from '@/routes/blog-posts-page'
import { EditBlogPostPage } from '@/routes/edit-blog-post-page'
import { EditPersonaPage } from '@/routes/edit-persona-page'
import { GenerateTextRunPage } from '@/routes/generate-text-run-page'
import { HomePage } from '@/routes/home-page'
import { InvitePage } from '@/routes/invite-page'
import { NewPersonaPage } from '@/routes/new-persona-page'
import { PersonaPage } from '@/routes/persona-page'
import { PersonasPage } from '@/routes/personas-page'
import { SignInPage } from '@/routes/sign-in-page'
import { WritePage } from '@/routes/write-page'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      {
        path: '/sign-in',
        element: <SignInPage />,
        handle: { isSignInCardHidden: true } satisfies AppRouteHandle,
      },
      {
        path: '/invite/:inviteCode',
        element: <InvitePage />,
        handle: { isSignInCardHidden: true } satisfies AppRouteHandle,
      },
      // Moves out of the guard in the public-reading PR
      {
        element: <RequireAuth />,
        children: [
          { path: '/account', element: <AccountPage /> },
          {
            element: <RequirePermission permission="PERSONA_WRITE" />,
            children: [
              { path: '/personas', element: <PersonasPage /> },
              { path: '/personas/new', element: <NewPersonaPage /> },
              { path: '/personas/:personaIdentity/edit', element: <EditPersonaPage /> },
            ],
          },
          {
            element: <RequirePermission permission="BLOG_POST_WRITE" />,
            children: [
              { path: '/posts', element: <BlogPostsPage /> },
              { path: '/posts/:blogPostIdentity/edit', element: <EditBlogPostPage /> },
            ],
          },
          {
            element: <RequirePermission permission="GENERATE_TEXT_RUN_WRITE" />,
            children: [
              { path: '/write', element: <WritePage /> },
              {
                path: '/write/runs/:runIdentity',
                element: <GenerateTextRunPage />,
                handle: { hasSidebar: true } satisfies AppRouteHandle,
              },
            ],
          },
          {
            element: (
              <RequirePermission permission="USER_READ" message="This page is for admins." />
            ),
            children: [
              {
                path: '/admin/users',
                element: <AdminUsersPage />,
                handle: { isFullWidth: true } satisfies AppRouteHandle,
              },
              {
                path: '/admin/users/:userIdentity',
                element: <AdminUserPage />,
                handle: { isFullWidth: true, hasSidebar: true } satisfies AppRouteHandle,
              },
            ],
          },
          {
            path: '/personas/:personaIdentity',
            element: <PersonaPage />,
            handle: { hasSidebar: true } satisfies AppRouteHandle,
          },
          { path: '/posts/:blogPostIdentity', element: <BlogPostPage /> },
        ],
      },
    ],
  },
])
