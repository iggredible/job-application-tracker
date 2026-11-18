import type { RouteObject } from 'react-router'

import { Layout } from '@/components/Layout'
import { ApplicationDetailPage } from '@/pages/ApplicationDetailPage'
import { ApplicationsPage } from '@/pages/ApplicationsPage'
import { InsightsPage } from '@/pages/InsightsPage'
import { ResumePage } from '@/pages/ResumePage'

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: '/', element: <ApplicationsPage /> },
      { path: '/applications/:id', element: <ApplicationDetailPage /> },
      { path: '/resume', element: <ResumePage /> },
      { path: '/insights', element: <InsightsPage /> },
    ],
  },
]
