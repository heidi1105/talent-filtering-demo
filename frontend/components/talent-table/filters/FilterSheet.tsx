'use client'

import { useEffect, type ReactNode } from 'react'
import { AgeRangeFilter } from './AgeRangeFilter'
import { MultiSelect } from './MultiSelect'
import { FollowerRangeFilter } from './FollowerRangeFilter'
import type { AgeRange, FollowerRange } from '../types'

interface FilterSheetProps {
  open: boolean
  onClose: () => void
  genders: string[]
  ageRange: AgeRange
  onAgeRangeChange: (v: AgeRange) => void
  genderFilter: string[]
  onGenderFilterChange: (v: string[]) => void
  professionFilter: string[]
  onProfessionFilterChange: (v: string[]) => void
  allProfessions: string[]
  brandFilter: string[]
  onBrandFilterChange: (v: string[]) => void
  allBrands: string[]
  groupFilter: string[]
  onGroupFilterChange: (v: string[]) => void
  allGroups: string[]
  followerRange: FollowerRange
  followerBound: number
  onFollowerRangeChange: (v: FollowerRange) => void
  activeCount: number
  onClearAll: () => void
  loading: boolean
  total: number
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-[10.5px] font-medium text-muted tracking-[0.6px] uppercase mb-1.5">{label}</p>
      {children}
    </div>
  )
}

// Mobile-only bottom sheet holding every filter. The desktop controls bar
// keeps its inline popovers; on a phone six of them wrapping across the top
// crowds out the list, so they move behind one button. Filters apply live as
// they change — the footer button only dismisses the sheet.
export function FilterSheet({
  open, onClose, genders,
  ageRange, onAgeRangeChange,
  genderFilter, onGenderFilterChange,
  professionFilter, onProfessionFilterChange, allProfessions,
  brandFilter, onBrandFilterChange, allBrands,
  groupFilter, onGroupFilterChange, allGroups,
  followerRange, followerBound, onFollowerRangeChange,
  activeCount, onClearAll, loading, total,
}: FilterSheetProps) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    // Stop the list behind the sheet from scrolling under it.
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', handler)
      document.body.style.overflow = previousOverflow
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[900] md:hidden">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-[2px]" onClick={onClose} />

      <div
        role="dialog"
        aria-modal="true"
        aria-label="Filters"
        className="absolute inset-x-0 bottom-0 flex flex-col max-h-[85vh] bg-surface border-t border-border2 rounded-t-2xl"
      >
        <header className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <button
            onClick={onClearAll}
            disabled={activeCount === 0}
            className="text-[12px] text-muted hover:text-text disabled:opacity-30 cursor-pointer transition-colors duration-150"
          >
            Clear all
          </button>
          <h2 className="text-[13px] font-semibold text-text">Filters</h2>
          <button
            onClick={onClose}
            aria-label="Close filters"
            className="w-7 h-7 flex items-center justify-center rounded-full bg-surface2 border border-border2 text-muted text-[11px] cursor-pointer"
          >
            ✕
          </button>
        </header>

        <div className="overflow-y-auto px-4 py-4 flex flex-col gap-4">
          <Row label="Gender">
            <MultiSelect
              options={genders}
              selected={genderFilter}
              onChange={onGenderFilterChange}
              placeholder="All Genders"
              inSheet
            />
          </Row>
          <Row label="Age"><AgeRangeFilter value={ageRange} onChange={onAgeRangeChange} inSheet /></Row>
          <Row label="Group">
            <MultiSelect
              options={allGroups}
              selected={groupFilter}
              onChange={onGroupFilterChange}
              placeholder="All Groups"
              searchable
              inSheet
            />
          </Row>
          <Row label="Profession">
            <MultiSelect
              options={allProfessions}
              selected={professionFilter}
              onChange={onProfessionFilterChange}
              placeholder="All Professions"
              inSheet
            />
          </Row>
          <Row label="Brand">
            <MultiSelect
              options={allBrands}
              selected={brandFilter}
              onChange={onBrandFilterChange}
              placeholder="All Brands"
              searchable
              inSheet
            />
          </Row>
          <Row label="Instagram followers">
            <FollowerRangeFilter
              value={followerRange}
              bound={followerBound}
              onChange={onFollowerRangeChange}
              inSheet
            />
          </Row>
        </div>

        <div className="border-t border-border p-4 pb-[max(1rem,env(safe-area-inset-bottom))] shrink-0">
          <button
            onClick={onClose}
            className="w-full bg-accent text-[#111] rounded py-2.5 text-[13px] font-semibold tracking-[0.2px] cursor-pointer hover:opacity-85 transition-opacity duration-150"
          >
            {loading ? 'Show results' : `Show ${total.toLocaleString()} result${total !== 1 ? 's' : ''}`}
          </button>
        </div>
      </div>
    </div>
  )
}
