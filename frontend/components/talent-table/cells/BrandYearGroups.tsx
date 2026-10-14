import type { TalentBrand } from '@/lib/supabaseClient'
import { groupBrandsByYear } from '@/lib/talentDisplay'
import { BrandPills } from './BrandPills'

/** The detail modal's brand layout: evidence year stated once in a dim gutter,
 *  that year's affiliations flowing beside it.
 *
 *  Coverage is heavily skewed — 44 of 506 talents have any affiliation at all,
 *  median 1 — but the two that carry the list are the ones worth designing for:
 *  17 affiliations across 4 distinct years, and 9 across 6. Printing the year on
 *  every pill restated 4 facts 17 times, which is what made the list hard to
 *  read through. The gutter costs a row per year and buys back a scannable
 *  recency order. */
export function BrandYearGroups({ brands }: { brands: TalentBrand[] | null | undefined }) {
  const groups = groupBrandsByYear(brands)
  if (groups.length === 0) return <span className="text-dim">—</span>

  return (
    <div className="flex flex-col gap-1.5">
      {groups.map(({ year, brands: yearBrands }) => (
        // Baseline alignment, not top: it lines the year up with the text
        // inside the first pill rather than with the pill's border box.
        <div key={year ?? 'undated'} className="flex items-baseline gap-2.5">
          <span className="shrink-0 w-9 font-mono text-[11px] text-dim">
            {year ?? '—'}
          </span>
          <div className="flex-1 min-w-0">
            <BrandPills brands={yearBrands} linkSource />
          </div>
        </div>
      ))}
    </div>
  )
}
