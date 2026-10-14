'use client'

import { useCallback, useEffect, useState } from 'react'
import { supabase, asTalentRows, type TalentRow } from '@/lib/supabaseClient'
import { CURRENT_YEAR } from '@/lib/talentDisplay'
import { COLUMN_CONFIG } from '@/components/talent-table/columns'
import type { AgeRange, FollowerRange, FlagFilter } from '@/components/talent-table/types'

interface UseTalentQueryParams {
  debouncedSearch: string
  genderFilter: string[]
  professionFilter: string[]
  brandFilter: string[]
  groupFilter: string[]
  debouncedAge: AgeRange
  debouncedFollowers: FollowerRange
  followerBound: number
  flagFilter: FlagFilter
}

export function useTalentQuery({
  debouncedSearch,
  genderFilter,
  professionFilter,
  brandFilter,
  groupFilter,
  debouncedAge,
  debouncedFollowers,
  followerBound,
  flagFilter,
}: UseTalentQueryParams) {
  const [talents, setTalents] = useState<TalentRow[]>([])
  const [total, setTotal]     = useState(0)
  const [loading, setLoading] = useState(true)
  const [pageSize, setPageSize] = useState(25)
  const [page, setPage]         = useState(1)
  // Default view is the most-followed talents first; rows with no Instagram
  // handle sort last (see the nullsFirst handling in the query below).
  const [sortKey, setSortKey]   = useState<keyof TalentRow>('instagram_followers')
  const [sortDir, setSortDir]   = useState<'asc' | 'desc'>('desc')

  // Reset to page 1 whenever any filter criterion or the page size changes.
  useEffect(() => {
    setPage(1)
  }, [debouncedSearch, genderFilter, professionFilter, brandFilter, groupFilter, debouncedAge, debouncedFollowers, flagFilter, pageSize])

  const fetchTalents = useCallback(async () => {
    setLoading(true)
    const from = (page - 1) * pageSize
    const to   = from + pageSize - 1

    let query = supabase
      .from('talents_search')
      .select('*', { count: 'exact' })
      .order(sortKey, {
        ascending: sortDir === 'asc',
        // Rows with a handle (a follower count) always precede rows without
        // one, regardless of sort direction — Postgres defaults to NULLS
        // FIRST on descending, which would otherwise surface no-handle rows.
        ...(sortKey === 'instagram_followers' ? { nullsFirst: false } : {}),
      })

    // Instagram sort: follower count first, name as the tiebreaker.
    if (sortKey === 'instagram_followers') {
      query = query.order('name_en', { ascending: true })
    }

    query = query.range(from, to)

    if (debouncedSearch.trim()) {
      // other_names is text[]; other_names_text (view-computed, space-joined)
      // lets it match the same ilike keyword search as the scalar columns.
      query = query.or(
        `name_en.ilike.%${debouncedSearch}%,name_native.ilike.%${debouncedSearch}%,` +
        `other_names_text.ilike.%${debouncedSearch}%,group_name.ilike.%${debouncedSearch}%`
      )
    }
    if (genderFilter.length)     query = query.in('gender', genderFilter)
    if (professionFilter.length) query = query.overlaps('occupation', professionFilter)
    if (brandFilter.length)      query = query.overlaps('brand_names', brandFilter)
    // group_name is a scalar column, not an array — match it by value.
    if (groupFilter.length)      query = query.in('group_name', groupFilter)
    if (debouncedAge.min !== '')  query = query.lte('birth_year', CURRENT_YEAR - parseInt(debouncedAge.min))
    if (debouncedAge.max !== '')  query = query.gte('birth_year', CURRENT_YEAR - parseInt(debouncedAge.max))
    if (debouncedFollowers.min > 0)             query = query.gte('instagram_followers', debouncedFollowers.min)
    if (debouncedFollowers.max < followerBound) query = query.lte('instagram_followers', debouncedFollowers.max)
    if (flagFilter === 'flagged')   query = query.not('remarks', 'is', null)
    if (flagFilter === 'unflagged') query = query.is('remarks', null)

    const { data, count, error } = await query
    if (!error) {
      // id/name_en/brand_names are guaranteed non-null by the schema — see TalentRow.
      setTalents(asTalentRows(data))
      setTotal(count || 0)
    }
    setLoading(false)
  }, [debouncedSearch, genderFilter, professionFilter, brandFilter, groupFilter, debouncedAge, debouncedFollowers, followerBound, flagFilter, page, pageSize, sortKey, sortDir])

  useEffect(() => { fetchTalents() }, [fetchTalents])

  const handleSort = (key: keyof TalentRow) => {
    if (!COLUMN_CONFIG.find((c) => c.key === key)?.sortable) return
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(key); setSortDir('asc') }
    setPage(1)
  }

  const totalPages = Math.ceil(total / pageSize)

  const pageButtons = Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
    if (totalPages <= 5)        return i + 1
    if (page <= 3)               return i + 1
    if (page >= totalPages - 2)  return totalPages - 4 + i
    return page - 2 + i
  })

  return {
    talents, total, loading,
    pageSize, setPageSize,
    page, setPage,
    sortKey, sortDir, handleSort,
    totalPages, pageButtons,
  }
}
