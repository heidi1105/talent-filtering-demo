'use client'

import { useState } from 'react'
import { AgeRangeFilter } from './filters/AgeRangeFilter'
import { MultiSelect } from './filters/MultiSelect'
import { FollowerRangeFilter } from './filters/FollowerRangeFilter'
import { FilterSheet } from './filters/FilterSheet'
import type { AgeRange, FollowerRange } from './types'

const PAGE_SIZE_OPTIONS = [25, 50, 100]
const GENDERS = ['Male', 'Female', 'Other']

interface ControlsBarProps {
  search: string
  onSearchChange: (v: string) => void
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
  loading: boolean
  total: number
  pageSize: number
  onPageSizeChange: (n: number) => void
}

export function ControlsBar({
  search, onSearchChange,
  ageRange, onAgeRangeChange,
  genderFilter, onGenderFilterChange,
  professionFilter, onProfessionFilterChange, allProfessions,
  brandFilter, onBrandFilterChange, allBrands,
  groupFilter, onGroupFilterChange, allGroups,
  followerRange, followerBound, onFollowerRangeChange,
  loading, total,
  pageSize, onPageSizeChange,
}: ControlsBarProps) {
  const [sheetOpen, setSheetOpen] = useState(false)

  // Counts filter *groups* in use, not individual selections — it labels the
  // mobile Filters button, where "3" should mean three filters are narrowing
  // the list, not three brands ticked inside one of them.
  const activeCount =
    (genderFilter.length > 0 ? 1 : 0) +
    (ageRange.min !== '' || ageRange.max !== '' ? 1 : 0) +
    (groupFilter.length > 0 ? 1 : 0) +
    (professionFilter.length > 0 ? 1 : 0) +
    (brandFilter.length > 0 ? 1 : 0) +
    (followerRange.min > 0 || followerRange.max < followerBound ? 1 : 0)

  const clearAll = () => {
    onGenderFilterChange([])
    onAgeRangeChange({ min: '', max: '' })
    onGroupFilterChange([])
    onProfessionFilterChange([])
    onBrandFilterChange([])
    onFollowerRangeChange({ min: 0, max: followerBound })
  }

  const resultLabel = loading ? '—' : `${total.toLocaleString()} result${total !== 1 ? 's' : ''}`

  const clearSearchBtn = search && (
    <button
      onClick={() => onSearchChange('')}
      aria-label="Clear search"
      className="absolute right-2 top-1/2 -translate-y-1/2 bg-transparent border-none text-muted cursor-pointer text-[11px] px-1 py-0.5 hover:text-text"
    >
      ✕
    </button>
  )

  return (
    <>
      {/* ── Mobile (<md): pill search + one Filters button ───────── */}
      <div className="md:hidden flex flex-col gap-2 mb-2.5">
        <div className="relative">
          <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted text-[17px] pointer-events-none select-none">
            ⌕
          </span>
          <input
            type="text"
            placeholder="Search by name or group name..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            // Held at 16px deliberately: anything smaller makes iOS Safari
            // zoom the page on focus. The pill height carries the size cut.
            className="w-full bg-surface2 border border-transparent rounded-full text-text font-sans text-base h-10 pl-10 pr-9 outline-none focus:border-accent transition-colors duration-150 placeholder:text-dim"
          />
          {clearSearchBtn}
        </div>

        <div className="flex items-center justify-between">
          <button
            onClick={() => setSheetOpen(true)}
            className={`flex items-center gap-1.5 border rounded-full text-[12px] py-1.5 px-3 cursor-pointer transition-colors duration-150 ${
              activeCount > 0
                ? 'bg-accent-dim border-accent text-accent'
                : 'bg-surface border-border text-text'
            }`}
          >
            <span className="text-[10px]">⚙</span>
            Filters{activeCount > 0 ? ` (${activeCount})` : ''}
          </button>
          <span className="text-[11px] text-muted font-mono">{resultLabel}</span>
        </div>
      </div>

      <FilterSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        genders={GENDERS}
        ageRange={ageRange}
        onAgeRangeChange={onAgeRangeChange}
        genderFilter={genderFilter}
        onGenderFilterChange={onGenderFilterChange}
        professionFilter={professionFilter}
        onProfessionFilterChange={onProfessionFilterChange}
        allProfessions={allProfessions}
        brandFilter={brandFilter}
        onBrandFilterChange={onBrandFilterChange}
        allBrands={allBrands}
        groupFilter={groupFilter}
        onGroupFilterChange={onGroupFilterChange}
        allGroups={allGroups}
        followerRange={followerRange}
        followerBound={followerBound}
        onFollowerRangeChange={onFollowerRangeChange}
        activeCount={activeCount}
        onClearAll={clearAll}
        loading={loading}
        total={total}
      />

      {/* ── Desktop (md+): unchanged inline controls ─────────────── */}
      <div className="hidden md:flex items-center gap-2.5 mb-4 flex-wrap">
        {/* Search */}
        <div className="relative flex-1 min-w-[220px] max-w-[360px]">
          <span className="absolute left-[11px] top-1/2 -translate-y-1/2 text-muted text-[17px] pointer-events-none select-none">
            ⌕
          </span>
          <input
            type="text"
            placeholder="Search by name or group name..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-surface border border-border rounded text-text font-sans text-[13.5px] py-2 pr-8 pl-[34px] outline-none focus:border-accent transition-colors duration-150 placeholder:text-dim"
          />
          {clearSearchBtn}
        </div>

        {/* Gender filter */}
        <MultiSelect
          options={GENDERS}
          selected={genderFilter}
          onChange={onGenderFilterChange}
          placeholder="All Genders"
        />

        {/* Age range filter */}
        <AgeRangeFilter value={ageRange} onChange={onAgeRangeChange} />

        {/* Group filter */}
        <MultiSelect
          options={allGroups}
          selected={groupFilter}
          onChange={onGroupFilterChange}
          placeholder="All Groups"
          searchable
        />

        {/* Profession filter */}
        <MultiSelect
          options={allProfessions}
          selected={professionFilter}
          onChange={onProfessionFilterChange}
          placeholder="All Professions"
        />

        {/* Brand filter */}
        <MultiSelect
          options={allBrands}
          selected={brandFilter}
          onChange={onBrandFilterChange}
          placeholder="All Brands"
          searchable
        />

        {/* Instagram follower range filter */}
        <FollowerRangeFilter value={followerRange} bound={followerBound} onChange={onFollowerRangeChange} />

        <span className="text-xs text-muted font-mono">{resultLabel}</span>

        {/* Page size */}
        <div className="flex items-center gap-1 ml-auto">
          <span className="text-xs text-muted mr-1">Show</span>
          {PAGE_SIZE_OPTIONS.map((n) => (
            <button
              key={n}
              onClick={() => onPageSizeChange(n)}
              className={`border rounded font-mono text-xs px-2.5 py-1.5 cursor-pointer transition-all duration-150 ${
                pageSize === n
                  ? 'bg-accent-dim border-accent text-accent'
                  : 'bg-surface border-border text-muted hover:border-border2 hover:text-text'
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>
    </>
  )
}
