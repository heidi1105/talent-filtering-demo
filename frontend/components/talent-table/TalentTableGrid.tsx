import { useState } from 'react'
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
import {
  SortableContext,
  horizontalListSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { TalentRow } from '@/lib/supabaseClient'
import type { ColumnDef, RenderCtx } from './columns'
import { SortIcon } from './SortIcon'
import { TalentCardList } from './TalentCardList'

interface TalentTableGridProps {
  activeColumns: ColumnDef[]
  onReorderColumn: (draggedKey: keyof TalentRow, targetKey: keyof TalentRow) => void
  sortKey: keyof TalentRow
  sortDir: 'asc' | 'desc'
  onSort: (key: keyof TalentRow) => void
  talents: TalentRow[]
  loading: boolean
  selected: Set<string>
  onToggleSelect: (id: string) => void
  onToggleSelectPage: () => void
  onOpenTalent: (talent: TalentRow) => void
}

interface SortableThProps {
  col: ColumnDef
  sortKey: keyof TalentRow
  sortDir: 'asc' | 'desc'
  onSort: (key: keyof TalentRow) => void
}

// Draggable + sortable header cell. Pointer/keyboard listeners live on the
// <th> itself: a plain click (no movement past the activation distance)
// still reaches onSort, while a press-and-drag past that threshold reorders.
function SortableTh({ col, sortKey, sortDir, onSort }: SortableThProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: col.key })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <th
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={() => col.sortable && onSort(col.key)}
      title="Drag to reorder"
      className={`px-[14px] py-[11px] text-left text-[11px] font-medium text-muted tracking-[0.6px] uppercase whitespace-nowrap select-none cursor-grab active:cursor-grabbing touch-none ${
        col.sortable ? 'hover:text-text' : ''
      } ${isDragging ? 'opacity-40 relative z-10' : ''}`}
    >
      <span className="flex items-center gap-[5px]">
        {col.label}
        {col.sortable && (
          <SortIcon direction={sortKey === col.key ? sortDir : null} />
        )}
      </span>
    </th>
  )
}

export function TalentTableGrid({
  activeColumns, onReorderColumn, sortKey, sortDir, onSort,
  talents, loading, selected, onToggleSelect, onToggleSelectPage, onOpenTalent,
}: TalentTableGridProps) {
  const pageAllSelected     = talents.length > 0 && talents.every((t) => selected.has(t.id))
  const pagePartialSelected = talents.some((t) => selected.has(t.id)) && !pageAllSelected

  const [activeKey, setActiveKey] = useState<keyof TalentRow | null>(null)
  const activeCol = activeColumns.find((c) => c.key === activeKey) ?? null

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const handleDragStart = (e: DragStartEvent) => setActiveKey(e.active.id as keyof TalentRow)

  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    setActiveKey(null)
    if (over && active.id !== over.id) {
      onReorderColumn(active.id as keyof TalentRow, over.id as keyof TalentRow)
    }
  }

  const cellClassFor = (col: ColumnDef) => {
    let cls = 'px-[14px] py-[10px] align-middle text-text '
    if (col.key === 'photo_url') cls += 'w-14'
    else if (col.key === 'name_en') cls += 'min-w-[100px] whitespace-nowrap'
    else if (col.isArray || col.key === 'remarks') cls += 'max-w-[200px] whitespace-normal'
    else cls += 'whitespace-nowrap'
    return cls
  }

  return (
    <DndContext
      id="talent-table-columns"
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setActiveKey(null)}
    >
      {/* Below md the table is swapped for a card list — column visibility,
          reordering and sorting are desktop-only affordances, so the mobile
          view takes only the data props. */}
      <TalentCardList
        talents={talents}
        loading={loading}
        selected={selected}
        onToggleSelect={onToggleSelect}
        onOpenTalent={onOpenTalent}
      />

      <div className="hidden md:block overflow-x-auto border border-border rounded-lg bg-surface flex-1">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="bg-surface2 border-b border-border">
              <th className="w-10 px-[14px] py-[11px]">
                <input
                  type="checkbox"
                  checked={pageAllSelected}
                  ref={(el) => { if (el) el.indeterminate = pagePartialSelected }}
                  onChange={onToggleSelectPage}
                  className="w-[15px] h-[15px] [accent-color:var(--accent)] cursor-pointer"
                />
              </th>
              <SortableContext items={activeColumns.map((c) => c.key)} strategy={horizontalListSortingStrategy}>
                {activeColumns.map((col) => (
                  <SortableTh key={col.key} col={col} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                ))}
              </SortableContext>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-b border-border last:border-b-0">
                  <td className="px-[14px] py-[10px]">
                    <div className="w-[15px] h-[15px] rounded-[3px] bg-surface2 animate-pulse" />
                  </td>
                  {activeColumns.map((col) => (
                    <td key={col.key} className="px-[14px] py-[10px]">
                      <div
                        className={`h-[13px] rounded bg-surface2 animate-pulse ${
                          col.key === 'name_en' ? 'w-[130px]' : 'w-[90px]'
                        }`}
                      />
                    </td>
                  ))}
                </tr>
              ))
            ) : talents.length === 0 ? (
              <tr>
                <td colSpan={activeColumns.length + 1} className="text-center py-16 text-muted text-sm">
                  No talents found.
                </td>
              </tr>
            ) : (
              talents.map((t) => {
                const isSelected  = selected.has(t.id)
                const displayName = t.group_name ? `${t.name_en} (${t.group_name})` : t.name_en
                const ctx: RenderCtx = { displayName }

                return (
                  <tr
                    key={t.id}
                    // Row click opens the detail card; selection for export is
                    // the checkbox cell's job alone.
                    onClick={() => onOpenTalent(t)}
                    className={`border-b border-border last:border-b-0 cursor-pointer transition-colors duration-100 ${
                      isSelected ? 'bg-selected' : 'hover:bg-white/[.025]'
                    }`}
                  >
                    {/* Checkbox */}
                    <td className="px-[14px] py-[10px] align-middle" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => onToggleSelect(t.id)}
                        className="w-[15px] h-[15px] [accent-color:var(--accent)] cursor-pointer"
                      />
                    </td>

                    {activeColumns.map((col) => (
                      <td key={col.key} className={cellClassFor(col)}>
                        {col.render(t, ctx)}
                      </td>
                    ))}
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      <DragOverlay>
        {activeCol ? (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface2 border border-border2 text-accent text-[11px] font-medium tracking-[0.4px] uppercase shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
            <span className="text-dim">⠿</span>
            {activeCol.label}
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
