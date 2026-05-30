import { createFileRoute } from '@tanstack/react-router'
import ForumPage from '@/pages/forums/index'

export const Route = createFileRoute('/forums/$forumKey')({
  component: ForumPage,
  validateSearch: (search: Record<string, unknown>) => ({
    page: Number(search.page) || 1,
    sort: (search.sort as string) || 'create_time',
    order: (search.order as string) || 'desc',
  }),
})
