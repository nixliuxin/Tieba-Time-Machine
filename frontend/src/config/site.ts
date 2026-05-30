export const siteConfig = {
  name: '贴吧归档阅读器',
  description: '浏览和搜索已归档的百度贴吧内容',
  url: 'http://localhost:5173',
  ogImage: '',
  favicon: '/favicons/favicon.ico',
  author: {
    name: 'Nix',
    email: '',
    twitter: '',
  },
  keywords: ['贴吧', '归档', '阅读器', 'tieba', 'archive'],
  links: {},
  navigation: {
    main: [
      { title: '首页', href: '/' },
      { title: '搜索', href: '/search' },
    ],
  },
} as const
