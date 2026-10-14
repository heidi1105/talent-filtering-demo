import { Fragment, useState } from 'react'
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { SortableContext, arrayMove, rectSortingStrategy, sortableKeyboardCoordinates } from '@dnd-kit/sortable'
import type { BrandConfidence, TalentRow } from '@/lib/supabaseClient'
import { DECK_TOKENS, TALENTS_PER_SLIDE, hex } from '@/lib/deckStyle'
import { PLACEHOLDER_IMG_LARGE } from '@/lib/talentDisplay'
import { TalentCard } from './TalentCard'

interface ExportCardGridProps {
  talents: TalentRow[]
  onReorder: (next: TalentRow[]) => void
  onRemove: (id: string) => void
  minBrandConfidence: BrandConfidence
  onMinBrandConfidenceChange: (value: BrandConfidence) => void
}

const BRAND_CONFIDENCE_OPTIONS: { value: BrandConfidence; label: string; hint: string }[] = [
  { value: 'high',   label: 'High only',   hint: 'Brand PR or a major outlet stating the deal outright. The safe default for a client deck.' },
  { value: 'medium', label: 'Include medium', hint: 'Adds single-source and implied affiliations. More coverage, and more that could be wrong.' },
]

// The cards are styled with the deck's own tokens rather than the app's, so
// this grid doubles as a live preview of what the exported slides will look
// like. There is no theme to choose any more: the deck is built into the
// deck template, which fixes the palette and type (see lib/deckStyle.ts).
export function ExportCardGrid({
  talents, onReorder, onRemove,
  minBrandConfidence, onMinBrandConfidenceChange,
}: ExportCardGridProps) {
  const tokens = DECK_TOKENS
  const [activeId, setActiveId] = useState<string | null>(null)
  const activeTalent = talents.find((t) => t.id === activeId) ?? null

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const handleDragStart = (e: DragStartEvent) => setActiveId(e.active.id as string)

  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    setActiveId(null)
    if (over && active.id !== over.id) {
      const oldIndex = talents.findIndex((t) => t.id === active.id)
      const newIndex = talents.findIndex((t) => t.id === over.id)
      if (oldIndex !== -1 && newIndex !== -1) {
        onReorder(arrayMove(talents, oldIndex, newIndex))
      }
    }
  }

  return (
    <div className="px-8 pb-12 print:!p-4">
      {/* Brand confidence floor — same placement rationale as the theme picker:
          it changes what the cards below show, so it sits with them. */}
      <div className="flex items-center gap-3 mb-5 print:hidden flex-wrap">
        <span className="text-[11px] text-muted tracking-[0.4px] uppercase">Brand confidence</span>
        <div className="flex items-center bg-surface2 border border-border rounded p-[3px] gap-[2px]">
          {BRAND_CONFIDENCE_OPTIONS.map(({ value, label, hint }) => (
            <button
              key={value}
              onClick={() => onMinBrandConfidenceChange(value)}
              title={hint}
              className={`rounded px-[10px] py-[5px] text-[12px] font-medium cursor-pointer transition-colors duration-150 ${
                minBrandConfidence === value ? 'bg-accent text-[#111]' : 'text-muted hover:text-text'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="text-[11px] text-dim">
          {minBrandConfidence === 'high'
            ? 'Only affiliations backed by brand PR or a major outlet reach the deck.'
            : 'Single-source and implied affiliations are included — check them before sending.'}
        </span>
      </div>

      {/* Preview canvas — background matches the theme's slide background so
          the cards read against the same backdrop they'll sit on in the deck. */}
      <div className="rounded-xl p-6 print:!p-0 print:rounded-none" style={{ backgroundColor: hex(tokens.slideBg) }}>
        <DndContext
          id="export-card-grid"
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={() => setActiveId(null)}
        >
          <SortableContext items={talents.map((t) => t.id)} strategy={rectSortingStrategy}>
            {talents.length === 0 ? (
              <p className="text-center py-16 text-[13px] print:hidden" style={{ color: hex(tokens.muted) }}>
                No talents selected. Go back to the table to add more.
              </p>
            ) : (
              <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-5 print:grid-cols-3 print:gap-[14px]">
                {talents.map((t, i) => (
                  <Fragment key={t.id}>
                    {i > 0 && i % TALENTS_PER_SLIDE === 0 && (
                      <div className="col-span-full flex items-center gap-2 -mb-1 print:hidden">
                        <span className="text-[10px] tracking-[0.5px] uppercase" style={{ color: hex(tokens.muted) }}>
                          Slide {Math.floor(i / TALENTS_PER_SLIDE) + 1}
                        </span>
                        <div className="h-px flex-1" style={{ backgroundColor: hex(tokens.border) }} />
                      </div>
                    )}
                    <TalentCard
                      talent={t}
                      tokens={tokens}
                      position={i + 1}
                      onRemove={() => onRemove(t.id)}
                      minBrandConfidence={minBrandConfidence}
                    />
                  </Fragment>
                ))}
              </div>
            )}
          </SortableContext>

          <DragOverlay>
            {activeTalent ? (
              <div
                className="flex items-center gap-2.5 pr-4 rounded-full border shadow-[0_8px_24px_rgba(0,0,0,0.5)] overflow-hidden"
                style={{ backgroundColor: hex(tokens.surface), borderColor: hex(tokens.border) }}
              >
                <img
                  src={activeTalent.photo_url || PLACEHOLDER_IMG_LARGE}
                  alt=""
                  className="w-8 h-8 object-cover object-top"
                />
                <span className="text-[12px] font-medium" style={{ color: hex(tokens.text) }}>
                  {activeTalent.name_en}
                </span>
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </div>
    </div>
  )
}
