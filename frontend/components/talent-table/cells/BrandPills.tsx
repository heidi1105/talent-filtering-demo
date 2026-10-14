import type { TalentBrand } from '@/lib/supabaseClient'

interface BrandPillsProps {
  // Nullable on purpose: `brands` is absent from every row until the v3 view is
  // applied, and CLAUDE.md's rule is that a missing child renders a fallback
  // rather than crashing the table.
  brands: TalentBrand[] | null | undefined
  /** Render at most this many, then a "+N" marker. Omit to render all. */
  limit?: number
  /** Link each pill to its source_url. Deliberately off in the table — a row
   *  there opens the modal on click, so an anchor inside it would fire both at
   *  once. */
  linkSource?: boolean
}

// Colour carries confidence: blue is the ordinary high-confidence case, so
// only the rows worth a second look draw the eye. A row the owner entered by
// hand has no AI confidence to report and reads as blue too — nothing about it
// is uncertain. Current vs past is not shown at all; see talentDisplay.ts.
const TIER_CLASS: Record<'high' | 'medium' | 'low', string> = {
  high:   'bg-brand-high-fill border-brand-high-line text-accent2',
  medium: 'bg-brand-medium-fill border-brand-medium-line text-warn',
  low:    'bg-brand-low-fill border-brand-low-line text-danger',
}

function tierOf(b: TalentBrand): 'high' | 'medium' | 'low' {
  if (b.extraction_method === 'manual') return 'high'
  return b.confidence ?? 'high'
}

const PILL = 'inline-block text-[11px] px-[7px] py-0.5 rounded-[20px] border mr-0.5 mb-0.5 whitespace-nowrap'

function tooltip(b: TalentBrand, linked: boolean): string {
  const parts: string[] = []
  if (b.evidence_year) parts.push(String(b.evidence_year))
  parts.push(
    b.extraction_method === 'manual'
      ? 'entered manually'
      : `${b.confidence ?? 'unrated'} confidence`,
  )
  if (linked) parts.push('click to open source')
  return `${b.name} — ${parts.join(' · ')}`
}

/** Brand affiliation pills, shared by the table cell and the detail modal so
 *  the two can't drift. Callers decide the set: the table passes
 *  brandsInWindow() capped at DECK_BRAND_LIMIT, the modal passes one year's
 *  worth at a time via BrandYearGroups. Pills carry the name alone — the
 *  evidence year lives in the modal's gutter and in the tooltip, since
 *  repeating it per pill is what made a long list unreadable. */
export function BrandPills({ brands, limit, linkSource = false }: BrandPillsProps) {
  const all = brands ?? []
  if (all.length === 0) return <span className="text-dim">—</span>

  const visible  = limit != null ? all.slice(0, limit) : all
  const overflow = all.length - visible.length

  return (
    <>
      {visible.map((b) => {
        // Not every affiliation has a source: a hand-entered brand may have no
        // URL at all. Those still render — just as plain pills, not links.
        const linked  = linkSource && !!b.source_url
        const className = `${PILL} ${TIER_CLASS[tierOf(b)]}`
        // One brand can recur across years, so the name alone isn't a stable key.
        const key = `${b.name}-${b.evidence_year ?? 'undated'}`

        return linked ? (
          <a
            key={key}
            href={b.source_url!}
            target="_blank"
            rel="noopener noreferrer"
            title={tooltip(b, true)}
            className={`${className} no-underline hover:opacity-75 transition-opacity duration-150`}
          >
            {b.name}
          </a>
        ) : (
          <span key={key} title={tooltip(b, false)} className={className}>
            {b.name}
          </span>
        )
      })}
      {overflow > 0 && (
        <span className="inline-block text-[11px] px-[7px] py-0.5 rounded-[20px] bg-surface2 border border-border text-dim font-mono mr-0.5 mb-0.5 whitespace-nowrap">
          +{overflow}
        </span>
      )}
    </>
  )
}
