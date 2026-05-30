export function preventBodyAriaHidden() {
  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      if (mutation.type === 'attributes' && mutation.attributeName === 'aria-hidden') {
        const target = mutation.target as HTMLElement
        if (target === document.body && target.getAttribute('aria-hidden') === 'true') {
          if (!hasLegitimateModal()) {
            target.removeAttribute('aria-hidden')
          }
        }
      }
    }
  })

  observer.observe(document.body, {
    attributes: true,
    attributeFilter: ['aria-hidden'],
  })

  return () => observer.disconnect()
}

function hasLegitimateModal(): boolean {
  const openDialogs = document.querySelectorAll('[data-open="true"], [data-state="open"]')
  return openDialogs.length > 0
}
