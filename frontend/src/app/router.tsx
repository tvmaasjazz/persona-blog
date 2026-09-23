import { createBrowserRouter } from 'react-router'

import { AppLayout } from '@/components/layout/app-layout'
import { HomePage } from '@/routes/home-page'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [{ path: '/', element: <HomePage /> }],
  },
])
