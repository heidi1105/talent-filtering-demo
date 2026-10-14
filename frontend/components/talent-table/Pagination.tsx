const BTN_PAG = 'bg-surface border border-border rounded text-muted font-mono text-xs py-[5px] px-2.5 cursor-pointer transition-all duration-[120ms] min-w-[32px] text-center hover:border-border2 hover:text-text disabled:opacity-30 disabled:cursor-default'

interface PaginationProps {
  page: number
  totalPages: number
  total: number
  pageSize: number
  pageButtons: number[]
  onPageChange: (page: number) => void
}

export function Pagination({ page, totalPages, total, pageSize, pageButtons, onPageChange }: PaginationProps) {
  return (
    <div className="flex items-center justify-between gap-3 pt-[14px]">
      <span className="text-xs text-muted font-mono">
        {total === 0
          ? 'No results'
          : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`}
      </span>

      {/* Mobile: the numbered strip doesn't fit, so prev/next around a
          page indicator. */}
      <div className="flex md:hidden items-center gap-2">
        <button disabled={page === 1} onClick={() => onPageChange(page - 1)} className={BTN_PAG}>‹</button>
        <span className="text-[11px] text-muted font-mono whitespace-nowrap">
          {totalPages === 0 ? '0 / 0' : `${page} / ${totalPages}`}
        </span>
        <button disabled={page === totalPages || totalPages === 0} onClick={() => onPageChange(page + 1)} className={BTN_PAG}>›</button>
      </div>

      <div className="hidden md:flex gap-1">
        <button disabled={page === 1} onClick={() => onPageChange(1)} className={BTN_PAG}>«</button>
        <button disabled={page === 1} onClick={() => onPageChange(page - 1)} className={BTN_PAG}>‹</button>
        {pageButtons.map((p) => (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={`border rounded font-mono text-xs py-[5px] px-2.5 cursor-pointer transition-all duration-[120ms] min-w-[32px] text-center ${
              page === p
                ? 'bg-accent-dim border-accent text-accent'
                : 'bg-surface border-border text-muted hover:border-border2 hover:text-text'
            }`}
          >
            {p}
          </button>
        ))}
        <button disabled={page === totalPages || totalPages === 0} onClick={() => onPageChange(page + 1)} className={BTN_PAG}>›</button>
        <button disabled={page === totalPages || totalPages === 0} onClick={() => onPageChange(totalPages)} className={BTN_PAG}>»</button>
      </div>
    </div>
  )
}
