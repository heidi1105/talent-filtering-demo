import type { TalentRow } from '@/lib/supabaseClient'
import type { FlagFilter } from './types'
import { ColumnSettings } from './filters/ColumnSettings'

interface TableHeaderProps {
  selectedCount: number
  onExport: () => void
  visibleColumns: (keyof TalentRow)[]
  onColumnsChange: (next: (keyof TalentRow)[]) => void
  flagFilter: FlagFilter
  onFlagFilterChange: (v: FlagFilter) => void
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}

export function TableHeader({
  selectedCount, onExport,
  visibleColumns, onColumnsChange,
  flagFilter, onFlagFilterChange,
  theme, onToggleTheme,
}: TableHeaderProps) {
  return (
    <header className="sticky top-0 z-20 bg-bg flex items-center justify-between py-3 md:py-7 border-b border-border mb-2.5 md:mb-5">
      <div className="flex items-center gap-2.5 md:gap-[14px] min-w-0">
        <span className="text-[20px] md:text-[22px] text-accent leading-none mt-0.5">✦</span>
        <div className="min-w-0">
          <h1 className="text-lg md:text-xl font-semibold tracking-[-0.3px] text-text truncate">Talent Roster</h1>
          {/* Subtitle is the first thing to go on a phone — the title alone
              already identifies the tool. */}
          <p className="hidden sm:block text-[11px] text-muted tracking-[0.5px] uppercase mt-0.5">
            Korean Talent Database — Internal
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 md:gap-3 shrink-0">
        {selectedCount > 0 && (
          <button
            onClick={onExport}
            className="bg-accent text-[#111] rounded px-3 md:px-4 py-2 text-[13px] font-semibold cursor-pointer tracking-[0.2px] whitespace-nowrap hover:opacity-85 transition-opacity duration-150 shadow-lg"
          >
            <span className="hidden sm:inline">Export Selected</span>
            <span className="sm:hidden">Export</span> ({selectedCount})
          </button>
        )}
        {/* Column picker only means something next to the table. */}
        <div className="hidden md:block">
          <ColumnSettings
            visible={visibleColumns}
            onChange={onColumnsChange}
            flagFilter={flagFilter}
            onFlagFilterChange={onFlagFilterChange}
          />
        </div>
        <button
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          className="bg-surface2 border border-border rounded w-8 h-8 flex items-center justify-center text-muted hover:text-text hover:border-border2 transition-colors duration-150 cursor-pointer text-[15px]"
        >
          {theme === 'dark' ? '☀' : '◑'}
        </button>
      </div>
    </header>
  )
}
