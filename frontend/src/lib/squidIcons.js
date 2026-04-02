import { SQUID_ICON_SVGS } from './squidIcons.generated.js'

function hashString(value) {
  let hash = 0
  const text = value || 'unassigned'
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) >>> 0
  }
  return hash
}

function svgToDataUrl(svg) {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

function sanitizeSvg(svg) {
  return svg
    .replace(/<style[\s\S]*?<\/style>/g, '')
    .replace(/<animateTransform[^>]*\/>/g, '')
    .replace(/<animate[^>]*\/>/g, '')
    .replace(/<rect x="8" y="8" width="124" height="124" rx="28"[^>]*\/>/g, '')
    .replace(/<circle class="sparkle"[^>]*\/>/g, '')
}

export const SQUID_ICONS = SQUID_ICON_SVGS.map((svg, index) => {
  const sanitized = sanitizeSvg(svg)
  return {
  id: `squid-${index + 1}`,
  svg: sanitized,
  dataUrl: svgToDataUrl(sanitized),
}
})

export function getSquidIconForArchetype(archetypeName) {
  const key = archetypeName || 'unassigned'
  return SQUID_ICONS[hashString(key) % SQUID_ICONS.length]
}

export function getSquidIconDataUrl(archetypeName) {
  return getSquidIconForArchetype(archetypeName).dataUrl
}
