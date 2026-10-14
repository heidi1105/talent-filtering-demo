'use client'

import { useEffect, useRef, useState } from 'react'
import type { AgeRange } from '../types'

interface AgeRangeFilterProps {
  value: AgeRange
  onChange: (next: AgeRange) => void
  /** Mobile filter sheet variant — see MultiSelect's `inSheet`. */
  inSheet?: boolean
}

// ── Age range filter ─────────────────────────────────────────
export function AgeRangeFilter({ value, onChange, inSheet = false }: AgeRangeFilterProps) {
  const [open, setOpen] = useState(false)
  const wrapRef         = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const isActive = value.min !== '' || value.max !== ''

  let label = 'All Ages'
  if (value.min !== '' && value.max !== '') label = `${value.min}–${value.max}`
  else if (value.min !== '')               label = `${value.min}+`
  else if (value.max !== '')               label = `Up to ${value.max}`

  const INPUT_CLS = 'w-full bg-surface2 border border-border rounded text-text text-[13px] px-2.5 py-1.5 outline-none focus:border-accent placeholder:text-dim [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none'

  return (
    <div className="relative" ref={wrapRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 border rounded font-sans text-[13px] py-2 px-3 cursor-pointer transition-colors duration-150 outline-none whitespace-nowrap ${
          inSheet ? 'w-full justify-between' : ''
        } ${
          isActive
            ? 'bg-accent-dim border-accent text-accent'
            : 'bg-surface border-border text-text hover:border-border2'
        }`}
      >
        {label}
        <span className="text-[9px] opacity-50 ml-0.5">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className={`bg-surface border border-border2 rounded-lg p-3 ${
          inSheet
            ? 'mt-2 w-full'
            : 'absolute top-full left-0 mt-1 w-[200px] z-50 shadow-[0_8px_24px_rgba(0,0,0,0.5)]'
        }`}>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <p className="text-[10px] text-dim uppercase tracking-[0.5px] mb-1.5">Min</p>
              <input
                type="number"
                min="1" max="99"
                value={value.min}
                onChange={(e) => onChange({ ...value, min: e.target.value })}
                placeholder="e.g. 20"
                className={INPUT_CLS}
              />
            </div>
            <span className="text-muted text-sm pb-[7px]">–</span>
            <div className="flex-1">
              <p className="text-[10px] text-dim uppercase tracking-[0.5px] mb-1.5">Max</p>
              <input
                type="number"
                min="1" max="99"
                value={value.max}
                onChange={(e) => onChange({ ...value, max: e.target.value })}
                placeholder="e.g. 40"
                className={INPUT_CLS}
              />
            </div>
          </div>

          {isActive && (
            <button
              onClick={() => { onChange({ min: '', max: '' }); setOpen(false) }}
              className="w-full text-[11px] text-muted hover:text-text mt-3 pt-2 border-t border-border cursor-pointer transition-colors duration-150"
            >
              Clear
            </button>
          )}
        </div>
      )}
    </div>
  )
}
