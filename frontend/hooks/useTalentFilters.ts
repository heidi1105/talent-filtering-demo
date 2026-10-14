'use client'

import { useEffect, useRef, useState } from 'react'
import { supabase } from '@/lib/supabaseClient'
import { niceFollowerBound } from '@/lib/talentDisplay'
import type { AgeRange, FollowerRange, FlagFilter } from '@/components/talent-table/types'

// The controlled vocab (PRD.md). Always offered even when a value happens to
// be unused in the current data; values found in the data that aren't listed
// here are appended, so the dropdown can't fall behind the pipeline again.
const KNOWN_PROFESSIONS = ['Actor', 'Actress', 'Singer', 'Rapper', 'Dancer', 'Model', 'MC', 'KOL', 'Others']

// Canonical order first, then anything unrecognised alphabetically, 'Others' last.
function orderProfessions(values: Set<string>): string[] {
  const known = KNOWN_PROFESSIONS.filter((p) => p !== 'Others' && values.has(p))
  const extra = [...values].filter((v) => !KNOWN_PROFESSIONS.includes(v)).sort()
  return [...known, ...extra, ...(values.has('Others') ? ['Others'] : [])]
}

export function useTalentFilters() {
  const [search, setSearch]                       = useState('')
  const [debouncedSearch, setDebouncedSearch]       = useState('')
  const [genderFilter, setGenderFilter]             = useState<string[]>([])
  const [professionFilter, setProfessionFilter]     = useState<string[]>([])
  const [brandFilter, setBrandFilter]               = useState<string[]>([])
  const [allBrands, setAllBrands]                   = useState<string[]>([])
  const [groupFilter, setGroupFilter]               = useState<string[]>([])
  const [allGroups, setAllGroups]                   = useState<string[]>([])
  const [allProfessions, setAllProfessions]         = useState<string[]>(KNOWN_PROFESSIONS)
  const [ageRange, setAgeRange]                     = useState<AgeRange>({ min: '', max: '' })
  const [debouncedAge, setDebouncedAge]             = useState<AgeRange>({ min: '', max: '' })
  const [followerBound, setFollowerBound]           = useState(0)
  const [followerRange, setFollowerRange]           = useState<FollowerRange>({ min: 0, max: 0 })
  const [debouncedFollowers, setDebouncedFollowers] = useState<FollowerRange>({ min: 0, max: 0 })
  // "Flagged" = has remarks. Lives in the column settings panel, not the
  // filter bar — see FlagFilter. Defaults to unflagged: remarks mark a talent
  // as needing attention, so the roster should hide them until asked for.
  const [flagFilter, setFlagFilter]                 = useState<FlagFilter>('unflagged')

  const debounceRef         = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const ageDebounceRef      = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const followerDebounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  // Load the unique brand names, groups and professions present in the data,
  // once on mount — one query serves all three dropdowns. Paginated: PostgREST
  // caps a single request at 1000 rows, and the table now has ~6.6k, so a
  // plain .select() silently dropped facet values (e.g. groups) whose members
  // all fell past row 1000.
  useEffect(() => {
    const PAGE_SIZE = 1000
    let cancelled = false

    async function loadFacets() {
      const rows: { brand_names: string[] | null; occupation: string[] | null; group_name: string | null }[] = []
      for (let from = 0; ; from += PAGE_SIZE) {
        const { data, error } = await supabase
          .from('talents_search')
          .select('brand_names, occupation, group_name')
          .range(from, from + PAGE_SIZE - 1)
        if (error || !data) break
        rows.push(...data)
        if (data.length < PAGE_SIZE) break
      }
      if (cancelled || rows.length === 0) return

      setAllBrands([...new Set(rows.flatMap((t) => t.brand_names || []))].sort())
      // group_name is null for soloists and for group rows themselves.
      setAllGroups([...new Set(rows.flatMap((t) => (t.group_name ? [t.group_name] : [])))].sort())
      setAllProfessions(orderProfessions(new Set([
        ...KNOWN_PROFESSIONS,
        ...rows.flatMap((t) => t.occupation || []),
      ])))
    }

    loadFacets()
    return () => { cancelled = true }
  }, [])

  // Derive the follower slider's upper bound from the highest Instagram
  // follower count currently in the data, once on mount.
  useEffect(() => {
    supabase
      .from('talents_search')
      .select('instagram_followers')
      .not('instagram_followers', 'is', null)
      .order('instagram_followers', { ascending: false })
      .limit(1)
      .then(({ data }) => {
        const bound = niceFollowerBound(data?.[0]?.instagram_followers || 0)
        setFollowerBound(bound)
        setFollowerRange({ min: 0, max: bound })
        setDebouncedFollowers({ min: 0, max: bound })
      })
  }, [])

  // Debounce search input 350ms
  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search)
    }, 350)
    return () => clearTimeout(debounceRef.current)
  }, [search])

  // Debounce age range inputs 350ms
  useEffect(() => {
    clearTimeout(ageDebounceRef.current)
    ageDebounceRef.current = setTimeout(() => {
      setDebouncedAge(ageRange)
    }, 350)
    return () => clearTimeout(ageDebounceRef.current)
  }, [ageRange])

  // Debounce follower range slider 350ms
  useEffect(() => {
    clearTimeout(followerDebounceRef.current)
    followerDebounceRef.current = setTimeout(() => {
      setDebouncedFollowers(followerRange)
    }, 350)
    return () => clearTimeout(followerDebounceRef.current)
  }, [followerRange])

  return {
    search, setSearch, debouncedSearch,
    genderFilter, setGenderFilter,
    professionFilter, setProfessionFilter, allProfessions,
    brandFilter, setBrandFilter, allBrands,
    groupFilter, setGroupFilter, allGroups,
    ageRange, setAgeRange, debouncedAge,
    followerBound, followerRange, setFollowerRange, debouncedFollowers,
    flagFilter, setFlagFilter,
  }
}
