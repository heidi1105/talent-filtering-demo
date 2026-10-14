'use client'

import { useEffect, useRef, useState } from 'react'
import type { TalentRow } from '@/lib/supabaseClient'
import type { FlagFilter } from '../types'
import { COLUMN_CONFIG, COLUMN_GROUPS, DEFAULT_VISIBLE_COLUMNS } from '../columns'

const FLAG_OPTIONS: { value: FlagFilter; label: string }[] = [
  { value: 'all',        label: 'Show all' },
  { value: 'unflagged',  label: 'Show only unflagged' },
  { value: 'flagged',    label: 'Show only flagged' },
]

interface ColumnSettingsProps {
  visible: (keyof TalentRow)[]
  onChange: (next: (keyof TalentRow)[]) => void
  flagFilter: FlagFilter
  onFlagFilterChange: (v: FlagFilter) => void
}

// ── Column visibility settings ──────────────────────────────
export function ColumnSettings({ visible, onChange, flagFilter, onFlagFilterChange }: ColumnSettingsProps) {
  const [open, setOpen] = useState(false)
  const wrapRef         = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const toggle = (key: keyof TalentRow) => onChange(
    visible.includes(key) ? visible.filter((k) => k !== key) : [...visible, key]
  )

  return (
    <div className="relative" ref={wrapRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        title="Column settings"
        className="bg-surface2 border border-border rounded w-8 h-8 flex items-center justify-center text-muted hover:text-text hover:border-border2 transition-colors duration-150 cursor-pointer text-[15px]"
      >
        ⚙
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-1 w-[560px] bg-surface border border-border2 rounded-lg z-50 shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
          <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border">
            <span className="text-[13px] text-muted flex-shrink-0" aria-hidden>⚑</span>
            {FLAG_OPTIONS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => onFlagFilterChange(value)}
                aria-pressed={flagFilter === value}
                className={`text-[11px] rounded-full border px-2.5 py-1 cursor-pointer transition-colors duration-150 ${
                  flagFilter === value
                    ? 'bg-accent-dim border-accent text-accent'
                    : 'bg-surface2 border-border text-muted hover:text-text hover:border-border2'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="max-h-[320px] overflow-y-auto grid grid-cols-3 gap-x-1 px-1 pb-1">
            {COLUMN_GROUPS.map((group) => (
              <div key={group.label} className="min-w-0">
                <p className="text-[10px] text-dim uppercase tracking-[0.5px] px-2 pt-2.5 pb-1.5">
                  {group.label}
                </p>
                {group.columns.map((col) => (
                  <label key={col.key} className="flex items-center gap-2.5 px-2 py-[7px] rounded cursor-pointer hover:bg-white/[.025]">
                    <input
                      type="checkbox"
                      checked={visible.includes(col.key)}
                      onChange={() => toggle(col.key)}
                      className="w-[13px] h-[13px] [accent-color:var(--accent)] cursor-pointer flex-shrink-0"
                    />
                    <span className="text-[12px] text-text truncate">{col.label}</span>
                  </label>
                ))}
              </div>
            ))}
          </div>
          <div className="border-t border-border p-2 flex gap-2">
            <button
              onClick={() => onChange(COLUMN_CONFIG.map((c) => c.key))}
              className="flex-1 text-[11px] text-muted hover:text-text py-1 cursor-pointer transition-colors duration-150"
            >
              Select all columns
            </button>
            <button
              onClick={() => onChange(DEFAULT_VISIBLE_COLUMNS)}
              className="flex-1 text-[11px] text-muted hover:text-text py-1 cursor-pointer transition-colors duration-150"
            >
              Default columns
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
