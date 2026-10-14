'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/components/auth/AuthProvider'
import type { TalentRow } from '@/lib/supabaseClient'
import { useTheme } from '@/hooks/useTheme'
import { useColumnVisibility } from '@/hooks/useColumnVisibility'
import { useTalentFilters } from '@/hooks/useTalentFilters'
import { useTalentQuery } from '@/hooks/useTalentQuery'
import { TableHeader } from '@/components/talent-table/TableHeader'
import { ControlsBar } from '@/components/talent-table/ControlsBar'
import { TalentTableGrid } from '@/components/talent-table/TalentTableGrid'
import { Pagination } from '@/components/talent-table/Pagination'
import { TalentDetailModal } from '@/components/talent-table/TalentDetailModal'

// ── Main component ───────────────────────────────────────────
export default function TalentTable() {
  // ── Auth guard ──────────────────────────────────────────────
  // Redirects to /login if no session. RLS is the real security layer;
  // this just prevents unauthenticated users from seeing an empty/broken table.
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login')
    }
  }, [user, authLoading, router])

  // While checking session (or redirecting), render nothing.
  // This prevents a flash of the empty table before the redirect fires.
  if (authLoading || !user) return null

  // ── Rest of component (unchanged) ───────────────────────────
  return <AuthenticatedTable />
}

function AuthenticatedTable() {
  const { theme, toggleTheme } = useTheme()
  const { visibleColumns, updateVisibleColumns, activeColumns, moveColumn } = useColumnVisibility()
  const filters = useTalentFilters()
  const query = useTalentQuery({
    debouncedSearch: filters.debouncedSearch,
    genderFilter: filters.genderFilter,
    professionFilter: filters.professionFilter,
    brandFilter: filters.brandFilter,
    groupFilter: filters.groupFilter,
    debouncedAge: filters.debouncedAge,
    debouncedFollowers: filters.debouncedFollowers,
    followerBound: filters.followerBound,
    flagFilter: filters.flagFilter,
  })

  const [selected, setSelected]     = useState<Set<string>>(new Set())
  // The row the detail card is open for. Holds the view row already in hand —
  // opening the card costs no extra query.
  const [openTalent, setOpenTalent] = useState<TalentRow | null>(null)

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleSelectPage = () => {
    const pageIds = query.talents.map((t) => t.id)
    const allSelected = pageIds.every((id) => selected.has(id))
    setSelected((prev) => {
      const next = new Set(prev)
      if (allSelected) pageIds.forEach((id) => next.delete(id))
      else pageIds.forEach((id) => next.add(id))
      return next
    })
  }

  // IDs only — the export page refetches them itself. This used to serialize
  // whole rows into `?data=`, which at ~1.8KB per row overran the 16KB
  // request-line limit at ~9 talents: Node answered 431 before Next routed the
  // request, so the new tab showed a bare browser error and this tab showed
  // nothing at all. Same fix POST /export/pptx already uses. At ~37 chars per
  // UUID the ceiling is now ~440 talents, well past any plausible deck.
  const handleExport = () => {
    if (selected.size === 0) return
    window.open(`/export?ids=${Array.from(selected).join(',')}`, '_blank')
  }

  return (
    <>
      {openTalent && (
        <TalentDetailModal talent={openTalent} onClose={() => setOpenTalent(null)} />
      )}

      <div className="min-h-screen flex flex-col max-w-[1600px] mx-auto px-4 md:px-6 pb-12">
        <TableHeader
          selectedCount={selected.size}
          onExport={handleExport}
          visibleColumns={visibleColumns}
          onColumnsChange={updateVisibleColumns}
          flagFilter={filters.flagFilter}
          onFlagFilterChange={filters.setFlagFilter}
          theme={theme}
          onToggleTheme={toggleTheme}
        />

        <ControlsBar
          search={filters.search}
          onSearchChange={filters.setSearch}
          ageRange={filters.ageRange}
          onAgeRangeChange={filters.setAgeRange}
          genderFilter={filters.genderFilter}
          onGenderFilterChange={filters.setGenderFilter}
          professionFilter={filters.professionFilter}
          onProfessionFilterChange={filters.setProfessionFilter}
          allProfessions={filters.allProfessions}
          brandFilter={filters.brandFilter}
          onBrandFilterChange={filters.setBrandFilter}
          allBrands={filters.allBrands}
          groupFilter={filters.groupFilter}
          onGroupFilterChange={filters.setGroupFilter}
          allGroups={filters.allGroups}
          followerRange={filters.followerRange}
          followerBound={filters.followerBound}
          onFollowerRangeChange={filters.setFollowerRange}
          loading={query.loading}
          total={query.total}
          pageSize={query.pageSize}
          onPageSizeChange={query.setPageSize}
        />

        <TalentTableGrid
          activeColumns={activeColumns}
          onReorderColumn={moveColumn}
          sortKey={query.sortKey}
          sortDir={query.sortDir}
          onSort={query.handleSort}
          talents={query.talents}
          loading={query.loading}
          selected={selected}
          onToggleSelect={toggleSelect}
          onToggleSelectPage={toggleSelectPage}
          onOpenTalent={setOpenTalent}
        />

        <Pagination
          page={query.page}
          totalPages={query.totalPages}
          total={query.total}
          pageSize={query.pageSize}
          pageButtons={query.pageButtons}
          onPageChange={query.setPage}
        />
      </div>
    </>
  )
}
