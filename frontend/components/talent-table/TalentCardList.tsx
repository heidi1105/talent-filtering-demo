'use client'

import type { TalentRow } from '@/lib/supabaseClient'
import {
  CURRENT_YEAR,
  PLACEHOLDER_IMG_SMALL,
  onImgErrorSmall,
  humanizeFollowers,
} from '@/lib/talentDisplay'

interface TalentCardListProps {
  talents: TalentRow[]
  loading: boolean
  selected: Set<string>
  onToggleSelect: (id: string) => void
  onOpenTalent: (talent: TalentRow) => void
}

const MAX_BRANDS = 3

// Mobile (<md) stand-in for the table. Eight-plus columns can't be read on a
// phone, so each talent collapses to a card: avatar, identity line, then the
// fields that actually drive a shortlisting decision. Same interaction
// contract as the table row — tapping the card opens the detail modal, and
// the checkbox is the only selection affordance.
export function TalentCardList({
  talents, loading, selected, onToggleSelect, onOpenTalent,
}: TalentCardListProps) {
  // No border/rounding on mobile — the cards' own dividers carry the
  // structure, and a framed panel inside a 16px gutter just eats width.
  const wrapCls = 'md:hidden bg-surface flex-1'

  if (loading) {
    return (
      <div className={wrapCls}>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 px-3 py-2.5 border-b border-border last:border-b-0">
            <div className="w-11 h-11 rounded-full bg-surface2 animate-pulse shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="h-[14px] w-[45%] rounded bg-surface2 animate-pulse" />
              <div className="h-[11px] w-[70%] rounded bg-surface2 animate-pulse mt-2" />
              <div className="h-[11px] w-[35%] rounded bg-surface2 animate-pulse mt-1.5" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (talents.length === 0) {
    return (
      <div className={wrapCls}>
        <p className="text-center py-16 text-muted text-[13px]">No talents found.</p>
      </div>
    )
  }

  return (
    <ul className={wrapCls}>
      {talents.map((t) => {
        const isSelected = selected.has(t.id)
        const brands     = t.brand_names || []

        // Age is null for groups (no birth_year) and gender/followers are
        // absent for plenty of rows — build the line from what exists rather
        // than rendering dashes for every gap.
        const meta = [
          t.gender,
          t.birth_year ? `${CURRENT_YEAR - t.birth_year}` : null,
          t.instagram_followers !== null ? `${humanizeFollowers(t.instagram_followers)} followers` : null,
          (t.occupation || []).join(', '),
        ].filter(Boolean).join(' · ')

        return (
          <li
            key={t.id}
            onClick={() => onOpenTalent(t)}
            className={`flex items-center gap-3 px-3 py-2.5 border-b border-border last:border-b-0 cursor-pointer transition-colors duration-100 ${
              isSelected ? 'bg-selected' : 'active:bg-white/[.04]'
            }`}
          >
            <img
              src={t.photo_url || PLACEHOLDER_IMG_SMALL}
              alt={t.name_en}
              // kprofiles.com blocks hotlinks by Referer (returns 403); sending
              // no referer makes it serve the image. Harmless for Wikimedia.
              referrerPolicy="no-referrer"
              onError={onImgErrorSmall}
              className="w-11 h-11 rounded-full object-cover object-top shrink-0 bg-surface2"
            />

            <div className="flex-1 min-w-0">
              <p className="text-[14px] font-semibold text-text truncate leading-snug">
                {t.name_en}
                {t.name_native && (
                  <span className="font-medium text-muted font-mono text-[12px] ml-1.5">
                    {t.name_native}
                  </span>
                )}
                {t.group_name && (
                  <span className="font-medium text-muted text-[12px] ml-1.5">
                    ({t.group_name})
                  </span>
                )}
              </p>

              {meta && (
                <p className="text-[12px] text-muted truncate mt-[2px]">{meta}</p>
              )}

              {brands.length > 0 && (
                <p className="mt-1 truncate">
                  {brands.slice(0, MAX_BRANDS).map((b) => (
                    <span
                      key={b}
                      className="inline-block text-[10px] px-[6px] py-0.5 rounded-[20px] bg-[rgba(110,157,200,0.08)] border border-[rgba(110,157,200,0.25)] text-accent2 mr-1 whitespace-nowrap"
                    >
                      {b}
                    </span>
                  ))}
                  {brands.length > MAX_BRANDS && (
                    <span className="inline-block text-[10px] px-[6px] py-0.5 rounded-[20px] bg-surface2 border border-border text-dim font-mono whitespace-nowrap">
                      +{brands.length - MAX_BRANDS}
                    </span>
                  )}
                </p>
              )}
            </div>

            {/* Padded so the tap target clears 44px without growing the box */}
            <label
              onClick={(e) => e.stopPropagation()}
              className="shrink-0 self-stretch flex items-center pl-2 pr-1 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => onToggleSelect(t.id)}
                aria-label={`Select ${t.name_en}`}
                className="w-[18px] h-[18px] [accent-color:var(--accent)] cursor-pointer"
              />
            </label>
          </li>
        )
      })}
    </ul>
  )
}
