'use client'

import { useEffect, useState } from 'react'
import { supabase, asTalentRows, type BrandConfidence, type TalentRow } from '@/lib/supabaseClient'
import { useTheme } from '@/hooks/useTheme'
import { ExportHeader } from '@/components/export/ExportHeader'
import { ExportCardGrid } from '@/components/export/ExportCardGrid'

export default function ExportPage() {
  const { theme, toggleTheme } = useTheme()
  const [talents, setTalents] = useState<TalentRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)
  const [pptxLoading, setPptxLoading] = useState(false)
  const [pptxError, setPptxError]     = useState(false)
  // Starts strict every time the page opens. Loosening the floor is a per-deck
  // judgement call, so it deliberately doesn't persist across exports.
  const [minBrandConfidence, setMinBrandConfidence] = useState<BrandConfidence>('high')

  const handleSavePptx = async () => {
    if (talents.length === 0 || pptxLoading) return
    setPptxLoading(true)
    setPptxError(false)
    try {
      // The route rejects requests without a valid Supabase session token.
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) throw new Error('Not signed in')
      const res = await fetch('/export/pptx', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`,
        },
        // Order here is the card order the user arranged on this page — the
        // route re-sorts its DB fetch to match this exact list.
        body: JSON.stringify({
          talentIds: talents.map((t) => t.id),
          minBrandConfidence,
        }),
      })
      if (!res.ok) throw new Error('Export failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'talents.pptx'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setPptxError(true)
    } finally {
      setPptxLoading(false)
    }
  }

  // The table hands over selected IDs and this page fetches the rows itself.
  // It used to receive whole rows inline in `?data=`, which overran the 16KB
  // request-line limit at ~9 talents — see the note on handleExport in
  // app/page.tsx. Fetching here also means a failure lands in this page's own
  // error state instead of a bare browser error page.
  useEffect(() => {
    const ids = (new URLSearchParams(window.location.search).get('ids') ?? '')
      .split(',')
      .filter(Boolean)

    if (ids.length === 0) {
      setError('No talents selected. Please use the Export button from the main table.')
      setLoading(false)
      return
    }

    let cancelled = false
    supabase
      .from('talents_search')
      .select('*')
      .in('id', ids)
      .then(({ data, error: queryError }) => {
        if (cancelled) return
        if (queryError) {
          setError('Could not load the selected talents. Please try exporting again.')
        } else {
          // `.in()` does not preserve the order of `ids` — restore the order the
          // rows were selected in, so the initial card layout is deterministic
          // rather than however Postgres happened to return them.
          const byId = new Map(asTalentRows(data).map((t) => [t.id, t]))
          const ordered = ids
            .map((id) => byId.get(id))
            .filter((t): t is TalentRow => t != null)
          if (ordered.length === 0) {
            setError('None of the selected talents could be found.')
          }
          setTalents(ordered)
        }
        setLoading(false)
      })

    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted text-sm animate-pulse">
        Loading selected talents…
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6 text-center text-muted text-sm">
        {error}
      </div>
    )
  }

  return (
    <>
      {/* Print styles — the one allowed exception to the no-style-tag rule */}
      <style>{`
        @media print {
          body {
            background: white !important;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          :root {
            --bg: white;
            --surface: #f5f5f5;
            --surface2: #ebebeb;
            --border: #ddd;
            --border2: #ccc;
            --text: #111;
            --text-muted: #444;
            --text-dim: #888;
            --accent: #8a6a2a;
            --accent2: #2a5a8a;
          }
        }
      `}</style>

      <div className="min-h-screen">
        <ExportHeader
          talentCount={talents.length}
          theme={theme}
          onToggleTheme={toggleTheme}
          onSavePptx={handleSavePptx}
          pptxLoading={pptxLoading}
          onSavePdf={() => window.print()}
        />

        {pptxError && (
          <p className="px-8 -mt-6 mb-6 text-[12px] text-muted print:hidden">
            ⚠ Failed to generate the PPTX file. Please try again.
          </p>
        )}

        <ExportCardGrid
          talents={talents}
          onReorder={setTalents}
          onRemove={(id) => setTalents((prev) => prev.filter((t) => t.id !== id))}
          minBrandConfidence={minBrandConfidence}
          onMinBrandConfidenceChange={setMinBrandConfidence}
        />
      </div>
    </>
  )
}
