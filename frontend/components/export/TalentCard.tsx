import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { BrandConfidence, TalentRow } from '@/lib/supabaseClient'
import { hex, type DeckTokens } from '@/lib/deckStyle'
import {
  PLACEHOLDER_IMG_LARGE,
  onImgErrorLarge,
  humanizeFollowers,
  followerTooltip,
  brandDeckCell,
  type DeckBrandCell,
} from '@/lib/talentDisplay'

type RowValue =
  | string
  | number
  | null
  | { kind: 'instagram'; handle: string; followers: number | null }
  | { kind: 'brands';    cell: DeckBrandCell }

interface TalentCardProps {
  talent: TalentRow
  tokens: DeckTokens
  // 1-based position in the current card order — mirrors the talent's slot
  // in the exported deck (see the "Slide N" grouping in ExportCardGrid).
  position: number
  onRemove: () => void
  /** Confidence floor the deck will apply — mirrored here so the preview and
   *  the generated file show the same affiliations. */
  minBrandConfidence: BrandConfidence
}

// One brand per line with its evidence year trailing in grey — the run layout
// brandCell in lib/pptxExport.ts emits, so the preview reads like the slide.
function BrandLines({ cell, tokens }: { cell: DeckBrandCell; tokens: DeckTokens }) {
  if (cell.lines.length === 0) return <>N/A</>

  return (
    <>
      {cell.lines.map(({ name, year }) => (
        <span key={`${name}-${year ?? 'undated'}`} className="block">
          {name}
          {year != null && (
            <span className="text-[11px] font-mono" style={{ color: hex(tokens.muted) }}>
              {' '}{year}
            </span>
          )}
        </span>
      ))}
      {cell.overflow > 0 && (
        <span className="block text-[11px]" style={{ color: hex(tokens.muted) }}>
          +{cell.overflow} more
        </span>
      )}
    </>
  )
}

// Rows mirror `talentTableRows` in lib/pptxExport.ts exactly — NAME (above,
// as the card heading) then AGE / OCCUPATION / INSTAGRAM / BRAND ASSOCIATION /
// REMARKS — so what's on screen here is what lands on the slide. REMARKS is
// always blank per CLAUDE.md (manually filled in PowerPoint after export) —
// shown greyed out so it reads as intentional, not missing data.
export function TalentCard({ talent, tokens, position, onRemove, minBrandConfidence }: TalentCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: talent.id })

  const photoSrc     = talent.photo_url || PLACEHOLDER_IMG_LARGE
  const displayName = talent.group_name
    ? `${talent.name_en} (${talent.group_name})`
    : talent.name_en

  const rows: { label: string; value: RowValue; blank?: boolean }[] = [
    { label: 'Age',        value: talent.age ?? '—' },
    { label: 'Occupation', value: (talent.occupation || []).join(', ') || '—' },
    {
      label: 'Instagram',
      value: talent.instagram_username
        ? { kind: 'instagram', handle: `@${talent.instagram_username}`, followers: talent.instagram_followers }
        : null,
    },
    {
      label: 'Brand Association',
      // Same helper, same cap, same grey trailing year as brandCell in
      // lib/pptxExport.ts. This card is the only preview of the deck, so any
      // divergence here shows the user a file that isn't the one they download.
      value: { kind: 'brands', cell: brandDeckCell(talent.brands, minBrandConfidence) },
    },
    { label: 'Remarks', value: 'Add after export', blank: true },
  ]

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    backgroundColor: hex(tokens.surface),
    borderColor: hex(tokens.border),
    color: hex(tokens.text),
    fontFamily: `"${tokens.bodyFont}", ui-sans-serif, sans-serif`,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`group/card relative rounded-[10px] overflow-hidden flex flex-col border select-none cursor-grab active:cursor-grabbing touch-none transition-shadow duration-150 ${
        isDragging ? 'opacity-40 z-10 shadow-[0_12px_32px_rgba(0,0,0,0.5)]' : ''
      }`}
    >
      {/* Photo is inset rather than edge-to-edge — leaves visible side margin,
          echoes the framed photo box (fill + bordered roundRect) pptxExport
          draws behind each photo rather than a full-bleed image. */}
      <div className="p-4 pb-0">
        <div
          className="relative w-full aspect-[3/4] overflow-hidden rounded-[6px] border"
          style={{ backgroundColor: hex(tokens.surface), borderColor: hex(tokens.border) }}
        >
          <span
            title="Deck position — drag the card to reorder"
            className="absolute top-2 left-2 z-10 w-6 h-6 rounded-full bg-black/60 text-white text-[11px] font-semibold flex items-center justify-center font-mono"
          >
            {position}
          </span>
          <button
            type="button"
            title="Remove from export"
            aria-label="Remove from export"
            // Stop the pointer event from ever reaching the card's own drag
            // listeners — otherwise a slightly-off click here could register
            // as a drag start instead of (or as well as) a click.
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => { e.stopPropagation(); onRemove() }}
            className="absolute top-2 right-2 z-10 w-6 h-6 rounded-full bg-black/60 text-white text-[13px] leading-none flex items-center justify-center hover:bg-black/80 cursor-pointer transition-colors duration-150 print:hidden"
          >
            ✕
          </button>
          <img
            src={photoSrc}
            alt={talent.name_en}
            className="w-full h-full object-cover object-top block transition-transform duration-300 group-hover/card:scale-[1.03] pointer-events-none"
            referrerPolicy="no-referrer"
            onError={onImgErrorLarge}
            draggable={false}
          />
        </div>
      </div>

      <div className="p-4 flex-1">
        <h2 className="text-[15px] font-semibold leading-[1.3]" style={{ fontFamily: `"${tokens.headingFont}", ui-sans-serif, sans-serif` }}>
          {displayName}
        </h2>
        {talent.name_native && (
          <p className="text-xs font-mono mt-[3px]" style={{ color: hex(tokens.muted) }}>{talent.name_native}</p>
        )}
        <div className="h-px my-3" style={{ backgroundColor: hex(tokens.border) }} />
        <table className="w-full border-collapse">
          <tbody>
            {rows.map(({ label, value, blank }, idx) => (
              <tr key={label}>
                <td
                  className={`text-[10.5px] uppercase tracking-[0.5px] font-semibold whitespace-nowrap pr-3 align-top w-[96px]${idx > 0 ? ' pt-[7px]' : ''}`}
                  style={{ color: hex(tokens.text) }}
                >
                  {label}
                </td>
                <td
                  className={`text-[12.5px] align-top leading-[1.4]${idx > 0 ? ' pt-[7px]' : ''}${blank ? ' italic' : ''}`}
                  style={{ color: blank ? hex(tokens.muted) : hex(tokens.text) }}
                >
                  {value === null || typeof value !== 'object' ? (
                    value ?? '—'
                  ) : value.kind === 'brands' ? (
                    <BrandLines cell={value.cell} tokens={tokens} />
                  ) : (
                    <>
                      <a
                        href={`https://instagram.com/${talent.instagram_username}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="no-underline font-mono text-xs hover:opacity-75"
                        style={{ color: hex(tokens.accent) }}
                      >
                        {value.handle}
                      </a>
                      {value.followers && (
                        <span
                          className="text-[11px] font-mono"
                          style={{ color: hex(tokens.muted) }}
                          title={followerTooltip(value.followers, talent.instagram_followers_captured_at)}
                        >
                          {' '}· {humanizeFollowers(value.followers)}
                        </span>
                      )}
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
