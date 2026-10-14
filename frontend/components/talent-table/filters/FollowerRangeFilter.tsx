'use client'

import { useEffect, useRef, useState } from 'react'
import { humanizeFollowers, parseFollowerInput } from '@/lib/talentDisplay'
import type { FollowerRange } from '../types'

interface FollowerBoundInputProps {
  value: number
  onCommit: (n: number) => void
}

// Typable follower-count field — accepts "25k" / "10M" shorthand (case
// insensitive) alongside plain numbers. Keeps its own draft text while
// focused so it doesn't fight the user mid-keystroke, and only commits
// (parses + clamps via onCommit) on blur/Enter. Reverts to the last valid
// value on unparseable input.
function FollowerBoundInput({ value, onCommit }: FollowerBoundInputProps) {
  const [draft, setDraft]     = useState(humanizeFollowers(value))
  const [focused, setFocused] = useState(false)

  useEffect(() => {
    if (!focused) setDraft(humanizeFollowers(value))
  }, [value, focused])

  const commit = () => {
    const parsed = parseFollowerInput(draft)
    if (parsed !== null) onCommit(parsed)
    else setDraft(humanizeFollowers(value))
  }

  return (
    <input
      type="text"
      inputMode="text"
      value={draft}
      onFocus={() => setFocused(true)}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => { setFocused(false); commit() }}
      onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }}
      className="w-16 bg-transparent border-none text-right text-[11px] text-muted font-mono outline-none focus:text-accent px-0 py-0"
    />
  )
}

interface FollowerRangeFilterProps {
  value: FollowerRange
  bound: number
  onChange: (next: FollowerRange) => void
  /** Mobile filter sheet variant — see MultiSelect's `inSheet`. */
  inSheet?: boolean
}

// ── Instagram follower range filter (dual slider) ───────────
export function FollowerRangeFilter({ value, bound, onChange, inSheet = false }: FollowerRangeFilterProps) {
  const [open, setOpen] = useState(false)
  const wrapRef         = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const isActive = value.min > 0 || value.max < bound

  let label = 'All Followers'
  if (isActive) label = `${humanizeFollowers(value.min)} – ${humanizeFollowers(value.max)}`

  const SLIDER_CLS = 'w-full h-1 [accent-color:var(--accent)] cursor-pointer'

  return (
    <div className="relative" ref={wrapRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={bound <= 0}
        className={`flex items-center gap-1.5 border rounded font-sans text-[13px] py-2 px-3 cursor-pointer transition-colors duration-150 outline-none whitespace-nowrap disabled:opacity-50 disabled:cursor-default ${
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
            : 'absolute top-full left-0 mt-1 w-[220px] z-50 shadow-[0_8px_24px_rgba(0,0,0,0.5)]'
        }`}>
          <div>
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] text-dim uppercase tracking-[0.5px]">Min</p>
              <FollowerBoundInput
                value={value.min}
                onCommit={(n) => onChange({ ...value, min: Math.max(0, Math.min(n, value.max)) })}
              />
            </div>
            <input
              type="range"
              min={0}
              max={bound}
              step={Math.max(1, Math.round(bound / 200))}
              value={value.min}
              onChange={(e) => onChange({ ...value, min: Math.min(Number(e.target.value), value.max) })}
              className={SLIDER_CLS}
            />
          </div>

          <div className="mt-3">
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] text-dim uppercase tracking-[0.5px]">Max</p>
              <FollowerBoundInput
                value={value.max}
                onCommit={(n) => onChange({ ...value, max: Math.min(bound, Math.max(n, value.min)) })}
              />
            </div>
            <input
              type="range"
              min={0}
              max={bound}
              step={Math.max(1, Math.round(bound / 200))}
              value={value.max}
              onChange={(e) => onChange({ ...value, max: Math.max(Number(e.target.value), value.min) })}
              className={SLIDER_CLS}
            />
          </div>

          {isActive && (
            <button
              onClick={() => { onChange({ min: 0, max: bound }); setOpen(false) }}
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
