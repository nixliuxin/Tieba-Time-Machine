import { createFileRoute } from '@tanstack/react-router'
import ThreadPage from '@/pages/threads/index'

export const Route = createFileRoute('/threads/$tid')({
  component: ThreadPage,
  validateSearch: (search: Record<string, unknown>) => ({
    page: Number(search.page) || 1,
  }),
})
