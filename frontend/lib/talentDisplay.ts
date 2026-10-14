import type { TalentBrand, BrandConfidence } from './supabaseClient'

export const CURRENT_YEAR = new Date().getFullYear()

// ─── Brand affiliation display policy ───────────────────────────────────────
// The view hands over the full 10-year set, already sorted newest-evidence
// first. Narrowing happens here so the table cell, the deck, and the deck's
// on-screen preview card share one definition instead of three. Nothing below
// re-sorts — the order is the view's to own.
//
// Affiliations render unlabelled: `status` was dropped from the display path
// (2026-08-12), so a past deal is indistinguishable from a current one here.

/** Display window. Storage keeps 10 years; the table and the deck show 5. */
export const BRAND_DISPLAY_WINDOW_YEARS = 5

/** Brands per deck cell before "+N more". Bounded by slide geometry: the
 *  table rows leave ~1.6in of growth before the footer, and a 12pt line that
 *  wraps in the 2.594in column costs ~0.19in. Three plus the marker fits; four
 *  collides once a long brand name wraps. */
export const DECK_BRAND_LIMIT = 3

const CONFIDENCE_RANK: Record<BrandConfidence, number> = { low: 1, medium: 2, high: 3 }

/** Affiliations inside the display window. Manual rows with no evidence_year
 *  are kept — the year is optional for them by CHECK constraint, and dropping
 *  them would silently hide hand-entered records. */
export function brandsInWindow(brands: TalentBrand[] | null | undefined): TalentBrand[] {
  const cutoff = CURRENT_YEAR - BRAND_DISPLAY_WINDOW_YEARS
  return (brands ?? []).filter(
    (b) => b.evidence_year == null || b.evidence_year >= cutoff,
  )
}

export interface BrandYearGroup {
  /** Null for manual rows with no evidence_year — always the trailing group. */
  year: number | null
  brands: TalentBrand[]
}

/** Splits affiliations into consecutive runs sharing an evidence_year, so the
 *  detail modal can state the year once in a gutter instead of on every pill.
 *  The view orders by `evidence_year desc nulls last, name`, so runs and
 *  distinct years coincide and nothing here re-sorts — the order stays the
 *  view's to own, and undated rows fall into one group at the end. */
export function groupBrandsByYear(
  brands: TalentBrand[] | null | undefined,
): BrandYearGroup[] {
  const groups: BrandYearGroup[] = []
  for (const brand of brands ?? []) {
    const current = groups[groups.length - 1]
    if (current && current.year === brand.evidence_year) current.brands.push(brand)
    else groups.push({ year: brand.evidence_year, brands: [brand] })
  }
  return groups
}

/** What the PPTX deck and its preview card render: the display window, plus a
 *  confidence floor defaulting to 'high' — see the precision-over-recall rule
 *  in CLAUDE.md, since this is the surface that reaches brand clients.
 *  Caller slices to DECK_BRAND_LIMIT; the full length is returned so it can
 *  size the "+N more" marker. */
export function brandsForDeck(
  brands: TalentBrand[] | null | undefined,
  minConfidence: BrandConfidence,
): TalentBrand[] {
  const floor = CONFIDENCE_RANK[minConfidence]
  return brandsInWindow(brands).filter((b) => {
    // Confidence rates how much to trust an AI web-research result, so it has
    // no bearing on a row the owner typed in — those clear any floor, and are
    // the reason this can't just be a null-safe rank comparison.
    if (b.extraction_method === 'manual') return true
    return b.confidence != null && CONFIDENCE_RANK[b.confidence] >= floor
  })
}

export interface DeckBrandLine {
  name: string
  /** Trailing evidence year, rendered grey. Null on manual rows, where the
   *  year is optional by CHECK constraint. */
  year: number | null
}

export interface DeckBrandCell {
  lines: DeckBrandLine[]
  /** How many eligible affiliations the DECK_BRAND_LIMIT cut off. */
  overflow: number
}

/** The deck's BRAND ASSOCIATION cell, resolved but not yet styled. Both the
 *  slide and the export preview card build their own runs from this, so the
 *  two agree on which brands appear, in what order, with which years, and
 *  where the cut is. Empty `lines` is the "N/A" case; callers render it. */
export function brandDeckCell(
  brands: TalentBrand[] | null | undefined,
  minConfidence: BrandConfidence,
): DeckBrandCell {
  const eligible = brandsForDeck(brands, minConfidence)
  const visible  = eligible.slice(0, DECK_BRAND_LIMIT)
  return {
    lines: visible.map((b) => ({ name: b.name, year: b.evidence_year })),
    overflow: eligible.length - visible.length,
  }
}

// Small (40x40) placeholder — table row avatars.
export const PLACEHOLDER_IMG_SMALL =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'%3E%3Crect width='40' height='40' fill='%23333'/%3E%3Ccircle cx='20' cy='15' r='7' fill='%23555'/%3E%3Cellipse cx='20' cy='34' rx='12' ry='9' fill='%23555'/%3E%3C/svg%3E"

// Large (120x120) placeholder — export cards.
export const PLACEHOLDER_IMG_LARGE =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'%3E%3Crect width='120' height='120' fill='%23222'/%3E%3Ccircle cx='60' cy='44' r='22' fill='%23333'/%3E%3Cellipse cx='60' cy='100' rx='36' ry='28' fill='%23333'/%3E%3C/svg%3E"

export function onImgErrorSmall(e: React.SyntheticEvent<HTMLImageElement>) {
  e.currentTarget.src = PLACEHOLDER_IMG_SMALL
}

export function onImgErrorLarge(e: React.SyntheticEvent<HTMLImageElement>) {
  e.currentTarget.src = PLACEHOLDER_IMG_LARGE
}

// Rounds a raw max follower count up to a friendly slider bound (nearest
// 100k, or nearest power-of-ten step above 1M) so the handle never sits at
// an arbitrary fetched number.
export function niceFollowerBound(n: number): number {
  if (n <= 0) return 100_000
  const magnitude = n < 1_000_000 ? 100_000 : 10 ** Math.floor(Math.log10(n))
  return Math.ceil(n / magnitude) * magnitude
}

export function humanizeFollowers(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(n % 1_000 === 0 ? 0 : 1)}K`
  return `${n}`
}

// Hover tooltip for a humanized follower count — full number plus the date
// the snapshot was captured, e.g. "7,243,153 followers\nLast captured: 2026-07-21".
export function followerTooltip(n: number, capturedAt: string | null): string {
  const lines = [`${n.toLocaleString()} followers`]
  if (capturedAt) lines.push(`Last captured: ${capturedAt.slice(0, 10)}`)
  return lines.join('\n')
}

// Parses shorthand follower counts typed by the user — "25k", "10M", plain
// "1200" — case-insensitively. Returns null when the text isn't a number.
export function parseFollowerInput(raw: string): number | null {
  const match = raw.trim().toLowerCase().replace(/,/g, '').match(/^(\d+(?:\.\d+)?)\s*(k|m)?$/)
  if (!match) return null
  const amount = parseFloat(match[1])
  if (Number.isNaN(amount)) return null
  const multiplier = match[2] === 'k' ? 1_000 : match[2] === 'm' ? 1_000_000 : 1
  return Math.round(amount * multiplier)
}
