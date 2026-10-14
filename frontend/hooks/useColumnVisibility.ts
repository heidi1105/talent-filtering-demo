'use client'

import { useEffect, useState } from 'react'
import type { TalentRow } from '@/lib/supabaseClient'
import { COLUMN_CONFIG, DEFAULT_VISIBLE_COLUMNS, DEFAULT_COLUMN_ORDER } from '@/components/talent-table/columns'

export function useColumnVisibility() {
  const [visibleColumns, setVisibleColumns] = useState<(keyof TalentRow)[]>(DEFAULT_VISIBLE_COLUMNS)
  const [columnOrder, setColumnOrder]       = useState<(keyof TalentRow)[]>(DEFAULT_COLUMN_ORDER)

  // Load column visibility + order prefs once on mount; unknown/stale keys
  // are dropped and newly-shipped columns fall back to their own default.
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('visibleColumns') ?? 'null')
      if (Array.isArray(saved)) {
        const validKeys = new Set(COLUMN_CONFIG.map((c) => c.key))
        setVisibleColumns(saved.filter((k) => validKeys.has(k)))
      }
    } catch {
      // ignore malformed/missing localStorage value, keep defaults
    }

    try {
      const saved = JSON.parse(localStorage.getItem('columnOrder') ?? 'null')
      if (Array.isArray(saved)) {
        const validKeys = new Set(COLUMN_CONFIG.map((c) => c.key))
        const known = saved.filter((k) => validKeys.has(k))
        // Newly-shipped columns not present in a saved order get appended.
        const missing = DEFAULT_COLUMN_ORDER.filter((k) => !known.includes(k))
        setColumnOrder([...known, ...missing])
      }
    } catch {
      // ignore malformed/missing localStorage value, keep defaults
    }
  }, [])

  const updateVisibleColumns = (next: (keyof TalentRow)[]) => {
    setVisibleColumns(next)
    localStorage.setItem('visibleColumns', JSON.stringify(next))
  }

  const updateColumnOrder = (next: (keyof TalentRow)[]) => {
    setColumnOrder(next)
    localStorage.setItem('columnOrder', JSON.stringify(next))
  }

  // Drag-and-drop reorder: pulls `draggedKey` out and reinserts it at
  // `targetKey`'s position.
  const moveColumn = (draggedKey: keyof TalentRow, targetKey: keyof TalentRow) => {
    if (draggedKey === targetKey) return
    const next = columnOrder.filter((k) => k !== draggedKey)
    const targetIndex = next.indexOf(targetKey)
    next.splice(targetIndex, 0, draggedKey)
    updateColumnOrder(next)
  }

  // Locked columns (Name) always render regardless of visibleColumns state.
  const activeColumns = columnOrder
    .filter((key) => {
      const col = COLUMN_CONFIG.find((c) => c.key === key)
      return col?.locked || visibleColumns.includes(key)
    })
    .map((key) => COLUMN_CONFIG.find((c) => c.key === key)!)

  return { visibleColumns, updateVisibleColumns, columnOrder, moveColumn, activeColumns }
}
