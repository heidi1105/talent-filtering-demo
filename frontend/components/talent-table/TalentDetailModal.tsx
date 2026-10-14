'use client'

import { useEffect, type ReactNode } from 'react'
import type { TalentRow } from '@/lib/supabaseClient'
import {
  CURRENT_YEAR,
  PLACEHOLDER_IMG_LARGE,
  onImgErrorLarge,
  humanizeFollowers,
  followerTooltip,
} from '@/lib/talentDisplay'
import { TagPills } from './cells/TagPills'
import { BrandYearGroups } from './cells/BrandYearGroups'

interface TalentDetailModalProps {
  talent: TalentRow
  onClose: () => void
}

interface SocialSpec {
  label: string
  handle: string | null
  followers: number | null
  capturedAt: string | null
  /** null when the stored handle can't be turned into a trustworthy URL. */
  href: string | null
}

// Instagram and Twitter are the only platforms where the stored handle IS the
// URL slug, so a link built from it always resolves. YouTube handles are
// display names ('홍길동 @gildong.'), and XHS/Douyin profile paths use an
// internal numeric id the handle doesn't contain — those render as plain text
// rather than as a link that 404s. The guard rejects handles carrying
// characters the platform's own slugs never contain.
const IG_SLUG      = /^[A-Za-z0-9._]{1,30}$/
const TWITTER_SLUG = /^[A-Za-z0-9_]{1,15}$/

function linkFor(handle: string | null, pattern: RegExp, base: string): string | null {
  if (!handle || !pattern.test(handle)) return null
  return `${base}/${handle}`
}

function YouTubeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <path
        fill="currentColor"
        d="M23.5 6.2a3.02 3.02 0 0 0-2.12-2.14C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.38.56A3.02 3.02 0 0 0 .5 6.2 31.6 31.6 0 0 0 0 12a31.6 31.6 0 0 0 .5 5.8 3.02 3.02 0 0 0 2.12 2.14C4.5 20.5 12 20.5 12 20.5s7.5 0 9.38-.56a3.02 3.02 0 0 0 2.12-2.14A31.6 31.6 0 0 0 24 12a31.6 31.6 0 0 0-.5-5.8ZM9.6 15.6V8.4l6.4 3.6-6.4 3.6Z"
      />
    </svg>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-border pt-3 mt-3 first:border-t-0 first:pt-0 first:mt-0">
      <h3 className="text-[11px] font-medium text-muted tracking-[0.6px] uppercase mb-2">
        {title}
      </h3>
      {children}
    </section>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 py-[3px]">
      <span className="w-[88px] sm:w-[120px] shrink-0 text-[12px] text-dim">{label}</span>
      <span className="flex-1 text-[13px] text-text min-w-0">{children}</span>
    </div>
  )
}

// Full record for one talent, opened by clicking its table row. Everything
// shown comes from the `talents_search` view — no extra query, no client-side
// join. Brands carry confidence/evidence_year via the view's `brands` jsonb,
// which is what lets this surface show all 10 stored years while the table
// shows 5. Many fields are null for most rows, so every one renders a dash
// fallback rather than disappearing.
export function TalentDetailModal({ talent, onClose }: TalentDetailModalProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const displayName = talent.group_name
    ? `${talent.name_en} (${talent.group_name})`
    : talent.name_en

  const age = talent.birth_year ? CURRENT_YEAR - talent.birth_year : null

  const socials: SocialSpec[] = [
    {
      label: 'Instagram',
      handle: talent.instagram_username,
      followers: talent.instagram_followers,
      capturedAt: talent.instagram_followers_captured_at,
      href: linkFor(talent.instagram_username, IG_SLUG, 'https://instagram.com'),
    },
    {
      label: 'Twitter',
      handle: talent.twitter_handle,
      followers: talent.twitter_followers,
      capturedAt: talent.twitter_followers_captured_at,
      href: linkFor(talent.twitter_handle, TWITTER_SLUG, 'https://twitter.com'),
    },
    {
      label: 'YouTube',
      handle: talent.youtube_handle,
      followers: talent.youtube_followers,
      capturedAt: talent.youtube_followers_captured_at,
      // Display name, not a URL slug (see note above) — the channel-id link
      // below is a best-effort guess, not guaranteed to resolve.
      href: talent.youtube_handle ? `https://www.youtube.com/channel/${talent.youtube_handle}` : null,
    },
    { label: 'XHS',      handle: talent.xhs_handle,     followers: talent.xhs_followers,     capturedAt: talent.xhs_followers_captured_at,     href: null },
    { label: 'Douyin',   handle: talent.douyin_handle,  followers: talent.douyin_followers,  capturedAt: talent.douyin_followers_captured_at,  href: null },
    { label: 'Weibo',    handle: talent.weibo_handle,   followers: talent.weibo_followers,   capturedAt: talent.weibo_followers_captured_at,   href: null },
  ].filter((s) => s.handle)

  return (
    <div
      className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center z-[1000] p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${talent.name_en} details`}
        className="relative bg-surface border border-border2 rounded-[10px] w-full max-w-[680px] max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute top-3 right-3 bg-surface2 border border-border2 rounded-full w-[26px] h-[26px] text-muted text-[11px] cursor-pointer flex items-center justify-center hover:text-text transition-colors duration-150"
        >
          ✕
        </button>

        {/* Header — photo + identity */}
        <div className="flex gap-4 p-5 pb-4">
          <img
            src={talent.photo_url || PLACEHOLDER_IMG_LARGE}
            alt={talent.name_en}
            // kprofiles.com blocks hotlinks by Referer (403); sending no
            // referer makes it serve the image. Harmless for Wikimedia photos.
            referrerPolicy="no-referrer"
            onError={onImgErrorLarge}
            className="w-[92px] sm:w-[112px] shrink-0 aspect-[3/4] object-cover object-top rounded bg-surface2 border border-border"
          />
          <div className="min-w-0 pr-8">
            <h2 className="text-[19px] font-semibold text-text leading-tight">{displayName}</h2>
            {talent.name_native && (
              <p className="text-[13px] text-muted font-mono mt-1">{talent.name_native}</p>
            )}
            {(talent.other_names || []).length > 0 && (
              <p className="text-[12px] text-dim mt-2 leading-relaxed">
                Also known as {(talent.other_names || []).join(', ')}
              </p>
            )}
          </div>
        </div>

        <div className="px-5 pb-5">
          <Section title="Identity">
            <Field label="Age">
              {age !== null ? `${age} (b. ${talent.birth_year})` : '—'}
            </Field>
            <Field label="Gender">{talent.gender || '—'}</Field>
            <Field label="Nationality">{talent.nationality || '—'}</Field>
            <Field label="Languages"><TagPills values={talent.languages_spoken} /></Field>
          </Section>

          <Section title="Career">
            <Field label="Profession"><TagPills values={talent.occupation} /></Field>
            <Field label="Group">{talent.group_name || '—'}</Field>
            <Field label="Debut year">{talent.debut_year || '—'}</Field>
            <Field label="Active countries"><TagPills values={talent.active_countries} /></Field>
          </Section>

          <Section title="Social">
            {socials.length === 0 ? (
              <p className="text-[13px] text-dim">No social accounts on record.</p>
            ) : (
              socials.map((s) => (
                <Field key={s.label} label={s.label}>
                  <span
                    className="flex items-baseline gap-2 flex-wrap"
                    title={s.followers !== null ? followerTooltip(s.followers, s.capturedAt) : undefined}
                  >
                    {s.href && s.label !== 'YouTube' ? (
                      <a
                        href={s.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent no-underline font-mono text-xs hover:opacity-75 transition-opacity duration-150"
                      >
                        @{s.handle}
                      </a>
                    ) : (
                      <span className="text-text font-mono text-xs">{s.handle}</span>
                    )}
                    {s.href && s.label === 'YouTube' && (
                      <a
                        href={s.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label="Open YouTube channel"
                        className="text-accent hover:opacity-75 transition-opacity duration-150 inline-flex items-center"
                      >
                        <YouTubeIcon />
                      </a>
                    )}
                    {s.followers !== null && (
                      <span className="text-dim text-[11px] font-mono">
                        {humanizeFollowers(s.followers)} followers
                      </span>
                    )}
                  </span>
                </Field>
              ))
            )}
          </Section>

          {/* The full 10-year set, uncapped and unfiltered — this is the one
              surface that shows everything on record. The table narrows to 5
              years and the deck additionally drops anything below high
              confidence, so a brand can legitimately appear here and nowhere
              else; the legend explains why rather than leaving it a mystery. */}
          <Section title="Brands">
            <BrandYearGroups brands={talent.brands} />
            {(talent.brands ?? []).length > 0 && (
              <p className="text-[11px] text-dim mt-3 leading-relaxed">
                Grouped by evidence date; click a brand to open its source.
                Colour marks source confidence:{' '}
                <span className="text-accent2">high</span>,{' '}
                <span className="text-warn">medium</span>,{' '}
                <span className="text-danger">low</span>. Only high-confidence
                affiliations go into the exported deck by default. AI-generated
                and accepted as reference, not verified fact.
              </p>
            )}
          </Section>

          <Section title="Remarks">
            <p className="text-[13px] text-text whitespace-pre-wrap leading-relaxed">
              {talent.remarks || '—'}
            </p>
          </Section>
        </div>
      </div>
    </div>
  )
}
