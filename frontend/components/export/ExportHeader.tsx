interface ExportHeaderProps {
  talentCount: number
  theme: 'dark' | 'light'
  onToggleTheme: () => void
  onSavePptx: () => void
  pptxLoading: boolean
  onSavePdf: () => void
}

// The app-chrome toolbar — title, selection count, app-wide dark/light
// toggle, and the two save actions. The PPTX deck-theme picker lives in
// ExportCardGrid instead (the "main component"), next to what it previews.
export function ExportHeader({
  talentCount, theme, onToggleTheme, onSavePptx, pptxLoading, onSavePdf,
}: ExportHeaderProps) {
  return (
    <div className="flex items-center justify-between px-8 py-5 border-b border-border mb-8 print:hidden">
      <div className="flex items-center gap-3">
        <span className="text-xl text-accent">✦</span>
        <div>
          <p className="text-base font-semibold text-text">Talent Export</p>
          <p className="text-[11px] text-muted tracking-[0.4px] uppercase mt-[1px]">
            {talentCount} talent{talentCount !== 1 ? 's' : ''} selected
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          className="bg-surface2 border border-border rounded w-8 h-8 flex items-center justify-center text-muted hover:text-text hover:border-border2 transition-colors duration-150 cursor-pointer text-[15px]"
        >
          {theme === 'dark' ? '☀' : '◑'}
        </button>

        <button
          onClick={onSavePptx}
          disabled={pptxLoading || talentCount === 0}
          className="bg-accent text-[#111] rounded px-5 py-[9px] font-sans text-[13px] font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {pptxLoading ? 'Generating…' : 'Save as PPTX'}
        </button>

        <button
          onClick={onSavePdf}
          className="bg-accent text-[#111] rounded px-5 py-[9px] font-sans text-[13px] font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150"
        >
          Save as PDF
        </button>
      </div>
    </div>
  )
}
