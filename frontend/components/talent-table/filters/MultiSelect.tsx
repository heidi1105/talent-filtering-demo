'use client'

import { useEffect, useRef, useState } from 'react'

interface MultiSelectProps {
  options: string[]
  selected: string[]
  onChange: (next: string[]) => void
  placeholder: string
  searchable?: boolean
  /**
   * Mobile filter sheet variant: full-width trigger, and the panel opens in
   * normal flow instead of as an absolute popover — a fixed-width popover
   * would be clipped by the sheet's scroll container.
   */
  inSheet?: boolean
}

// ── Generic multi-select dropdown ───────────────────────────
export function MultiSelect({ options, selected, onChange, placeholder, searchable = false, inSheet = false }: MultiSelectProps) {
  const [open, setOpen]     = useState(false)
  const [search, setSearch] = useState('')
  const wrapRef             = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered     = searchable
    ? options.filter((o) => o.toLowerCase().includes(search.toLowerCase()))
    : options
  const allSelected  = filtered.length > 0 && filtered.every((o) => selected.includes(o))
  const someSelected = filtered.some((o) => selected.includes(o)) && !allSelected

  const toggle = (opt: string) => onChange(
    selected.includes(opt) ? selected.filter((o) => o !== opt) : [...selected, opt]
  )

  const toggleAll = () => {
    if (allSelected) onChange(selected.filter((o) => !filtered.includes(o)))
    else onChange([...new Set([...selected, ...filtered])])
  }

  const label = selected.length === 0 ? placeholder : `${selected.length} selected`

  return (
    <div className="relative" ref={wrapRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 border rounded font-sans text-[13px] py-2 px-3 cursor-pointer transition-colors duration-150 outline-none whitespace-nowrap ${
          inSheet ? 'w-full justify-between' : ''
        } ${
          selected.length > 0
            ? 'bg-accent-dim border-accent text-accent'
            : 'bg-surface border-border text-text hover:border-border2'
        }`}
      >
        {label}
        <span className="text-[9px] opacity-50 ml-0.5">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className={`bg-surface border border-border2 rounded-lg ${
          inSheet
            ? 'mt-2 w-full'
            : 'absolute top-full left-0 mt-1 min-w-full z-50 shadow-[0_8px_24px_rgba(0,0,0,0.5)]'
        }`}>
          {searchable && (
            <div className="p-2 border-b border-border">
              <input
                autoFocus
                type="text"
                placeholder={`Search ${placeholder.toLowerCase()}...`}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-surface2 border border-border rounded text-text text-[12px] px-2.5 py-1.5 outline-none focus:border-accent placeholder:text-dim"
              />
            </div>
          )}

          <div className="max-h-[240px] overflow-y-auto">
            <label className="flex items-center gap-2.5 px-3 py-2 cursor-pointer hover:bg-white/[.025] border-b border-border">
              <input
                type="checkbox"
                checked={allSelected}
                ref={(el) => { if (el) el.indeterminate = someSelected }}
                onChange={toggleAll}
                className="w-[13px] h-[13px] [accent-color:var(--accent)] cursor-pointer flex-shrink-0"
              />
              <span className="text-[12px] text-muted font-medium">
                {searchable && search ? 'Select all results' : 'Select all'}
              </span>
            </label>

            {filtered.map((opt) => (
              <label key={opt} className="flex items-center gap-2.5 px-3 py-[7px] cursor-pointer hover:bg-white/[.025]">
                <input
                  type="checkbox"
                  checked={selected.includes(opt)}
                  onChange={() => toggle(opt)}
                  className="w-[13px] h-[13px] [accent-color:var(--accent)] cursor-pointer flex-shrink-0"
                />
                <span className="text-[12px] text-text truncate">{opt}</span>
              </label>
            ))}

            {filtered.length === 0 && (
              <p className="text-[12px] text-dim text-center px-3 py-4">No results</p>
            )}
          </div>

          {selected.length > 0 && (
            <div className="border-t border-border p-2">
              <button
                onClick={() => { onChange([]); setOpen(false) }}
                className="w-full text-[11px] text-muted hover:text-text py-1 cursor-pointer transition-colors duration-150"
              >
                Clear selection
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
