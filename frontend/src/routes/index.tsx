import { createFileRoute } from '@tanstack/react-router'
import Home from '@/pages/home/index'

export const Route = createFileRoute('/')({
  component: Home,
})
