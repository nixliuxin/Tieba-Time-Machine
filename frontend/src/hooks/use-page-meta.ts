import { useEffect } from 'react'
import { metadataConfig, structuredData } from '@/config/metadata'

interface PageMetaOptions {
  description?: string
  /**
   * Whether to include structured data (JSON-LD)
   * @default false - only set on root level
   */
  includeStructuredData?: boolean
  /** Additional JSON-LD structured data to append (e.g. BlogPosting) */
  jsonLd?: Record<string, unknown>
  keywords?: string[]
  ogDescription?: string
  ogImage?: string
  ogTitle?: string
  ogType?: string
  ogUrl?: string
  title?: string
  twitterDescription?: string
  twitterImage?: string
  twitterTitle?: string
}

// Regex patterns for parsing selectors
const PROPERTY_REGEX = /property="([^"]+)"/
const NAME_REGEX = /name="([^"]+)"/

// Helper function to create or update meta tags
function updateMetaTag(selector: string, content: string, attribute = 'content') {
  let element = document.querySelector(selector) as HTMLMetaElement
  if (!element) {
    element = document.createElement('meta')
    if (selector.includes('property=')) {
      const property = selector.match(PROPERTY_REGEX)?.[1]
      if (property) {
        element.setAttribute('property', property)
      }
    } else if (selector.includes('name=')) {
      const name = selector.match(NAME_REGEX)?.[1]
      if (name) {
        element.setAttribute('name', name)
      }
    }
    document.head.appendChild(element)
  }
  element.setAttribute(attribute, content)
}

// Helper function to set structured data
function setStructuredData() {
  let structuredDataScript = document.querySelector(
    'script[type="application/ld+json"]'
  ) as HTMLScriptElement
  if (!structuredDataScript) {
    structuredDataScript = document.createElement('script')
    structuredDataScript.type = 'application/ld+json'
    document.head.appendChild(structuredDataScript)
  }
  structuredDataScript.textContent = JSON.stringify([
    structuredData.organization,
    structuredData.website,
  ])
}

function applyPageMetaTags(options: PageMetaOptions) {
  if (options.title) {
    document.title = metadataConfig.title.template.replace('%s', options.title)
  }

  const description = options.description || metadataConfig.description
  const keywords = options.keywords || metadataConfig.keywords
  const ogTitle = options.ogTitle || options.title || metadataConfig.openGraph.title
  const ogDescription = options.ogDescription || description
  const ogImage = options.ogImage || metadataConfig.openGraph.images[0].url
  const twitterTitle = options.twitterTitle || options.title || metadataConfig.twitter.title
  const twitterDescription = options.twitterDescription || description
  const twitterImage = options.twitterImage || ogImage

  updateMetaTag('meta[name="description"]', description)
  updateMetaTag(
    'meta[name="keywords"]',
    Array.isArray(keywords) ? keywords.join(', ') : String(keywords)
  )
  updateMetaTag('meta[name="author"]', metadataConfig.creator)
  updateMetaTag('meta[name="robots"]', 'index, follow')

  updateMetaTag('meta[property="og:type"]', metadataConfig.openGraph.type)
  updateMetaTag('meta[property="og:locale"]', metadataConfig.openGraph.locale)
  updateMetaTag('meta[property="og:site_name"]', metadataConfig.openGraph.siteName)
  updateMetaTag('meta[property="og:title"]', ogTitle)
  updateMetaTag('meta[property="og:description"]', ogDescription)
  updateMetaTag(
    'meta[property="og:image"]',
    ogImage.startsWith('http') ? ogImage : `${metadataConfig.openGraph.url}${ogImage}`
  )
  updateMetaTag(
    'meta[property="og:image:width"]',
    metadataConfig.openGraph.images[0].width.toString()
  )
  updateMetaTag(
    'meta[property="og:image:height"]',
    metadataConfig.openGraph.images[0].height.toString()
  )
  updateMetaTag('meta[property="og:image:alt"]', metadataConfig.openGraph.images[0].alt)
  updateMetaTag('meta[property="og:url"]', options.ogUrl || window.location.href)

  updateMetaTag('meta[name="twitter:card"]', metadataConfig.twitter.card)
  updateMetaTag('meta[name="twitter:site"]', metadataConfig.twitter.site || '')
  updateMetaTag('meta[name="twitter:creator"]', metadataConfig.twitter.creator || '')
  updateMetaTag('meta[name="twitter:title"]', twitterTitle)
  updateMetaTag('meta[name="twitter:description"]', twitterDescription)
  updateMetaTag(
    'meta[name="twitter:image"]',
    twitterImage.startsWith('http')
      ? twitterImage
      : `${metadataConfig.openGraph.url}${twitterImage}`
  )

  if (options.ogType) {
    updateMetaTag('meta[property="og:type"]', options.ogType)
  }

  // Set canonical link
  const canonicalUrl = options.ogUrl || window.location.href
  let canonicalLink = document.querySelector('link[rel="canonical"]') as HTMLLinkElement
  if (!canonicalLink) {
    canonicalLink = document.createElement('link')
    canonicalLink.rel = 'canonical'
    document.head.appendChild(canonicalLink)
  }
  canonicalLink.href = canonicalUrl

  if (options.includeStructuredData) {
    setStructuredData()
  }

  // Set page-specific JSON-LD
  if (options.jsonLd) {
    let pageJsonLd = document.querySelector('script[data-page-jsonld]') as HTMLScriptElement
    if (!pageJsonLd) {
      pageJsonLd = document.createElement('script')
      pageJsonLd.type = 'application/ld+json'
      pageJsonLd.setAttribute('data-page-jsonld', 'true')
      document.head.appendChild(pageJsonLd)
    }
    pageJsonLd.textContent = JSON.stringify(options.jsonLd)
  }
}

export function usePageMeta(options: PageMetaOptions = {}) {
  useEffect(() => {
    applyPageMetaTags(options)
    return () => {
      document.title = metadataConfig.title.default
      // Clean up page-specific JSON-LD
      const pageJsonLd = document.querySelector('script[data-page-jsonld]')
      if (pageJsonLd) pageJsonLd.remove()
      // Clean up canonical link
      const canonical = document.querySelector('link[rel="canonical"]')
      if (canonical) canonical.remove()
    }
  }, [options])
}

// Backward compatibility hook
export function usePageTitle(title?: string) {
  usePageMeta({ title })
}

// Imperative API for cases where hooks can't be used
export function setPageMeta(meta: PageMetaOptions) {
  // Set title
  if (meta.title) {
    document.title = metadataConfig.title.template.replace('%s', meta.title)
  }

  // Get effective values with fallbacks
  const description = meta.description || metadataConfig.description
  const keywords = meta.keywords || metadataConfig.keywords
  const ogTitle = meta.ogTitle || meta.title || metadataConfig.openGraph.title
  const ogDescription = meta.ogDescription || description
  const ogImage = meta.ogImage || metadataConfig.openGraph.images[0].url
  const twitterTitle = meta.twitterTitle || meta.title || metadataConfig.twitter.title
  const twitterDescription = meta.twitterDescription || description
  const twitterImage = meta.twitterImage || ogImage

  // Set all meta tags
  updateMetaTag('meta[name="description"]', description)
  updateMetaTag(
    'meta[name="keywords"]',
    Array.isArray(keywords) ? keywords.join(', ') : String(keywords)
  )
  updateMetaTag('meta[property="og:title"]', ogTitle)
  updateMetaTag('meta[property="og:description"]', ogDescription)
  updateMetaTag(
    'meta[property="og:image"]',
    ogImage.startsWith('http') ? ogImage : `${metadataConfig.openGraph.url}${ogImage}`
  )
  updateMetaTag('meta[property="og:url"]', meta.ogUrl || window.location.href)
  updateMetaTag('meta[name="twitter:title"]', twitterTitle)
  updateMetaTag('meta[name="twitter:description"]', twitterDescription)
  updateMetaTag(
    'meta[name="twitter:image"]',
    twitterImage.startsWith('http')
      ? twitterImage
      : `${metadataConfig.openGraph.url}${twitterImage}`
  )

  if (meta.includeStructuredData) {
    setStructuredData()
  }
}
