import type { ReactNode } from 'react'
import type { TalentRow } from '@/lib/supabaseClient'
import {
  CURRENT_YEAR,
  DECK_BRAND_LIMIT,
  PLACEHOLDER_IMG_SMALL,
  brandsInWindow,
  onImgErrorSmall,
} from '@/lib/talentDisplay'
import { TagPills } from './cells/TagPills'
import { BrandPills } from './cells/BrandPills'
import { RemarksLabel } from './cells/RemarksLabel'
import { SocialCell } from './cells/SocialCell'
import { CopyIdCell } from './cells/CopyIdCell'

export interface RenderCtx {
  displayName: string
}

export interface ColumnDef {
  key: keyof TalentRow
  label: string
  sortable: boolean
  defaultVisible?: boolean
  isArray?: boolean
  /** Always visible, excluded from the show/hide picker — but still reorderable. */
  locked?: boolean
  render: (t: TalentRow, ctx: RenderCtx) => ReactNode
}

// Single source of truth for every column: header label/sort, cell render,
// and default visibility. The picker toggles `visibleColumns` against these
// keys; the checkbox column is hardcoded and not listed here. Name is
// `locked` — always shown, not in the picker — but still drag-reorderable.
export const COLUMN_CONFIG: ColumnDef[] = [
  { key: 'name_en',               label: 'Name',                 sortable: true,  defaultVisible: true, locked: true,
    render: (t, ctx) => (
      <>
        <span className="block font-medium text-text">{ctx.displayName}</span>
        {t.name_native && (
          <span className="block text-[11.5px] text-muted mt-[1px] font-mono">
            {t.name_native}
          </span>
        )}
        {t.remarks && (
          <span className="block">
            <RemarksLabel remarks={t.remarks} />
          </span>
        )}
      </>
    ) },

  // Default-visible. This block's order is also the default left-to-right
  // table order (DEFAULT_COLUMN_ORDER is derived from it).
  // No enlarge affordance here — clicking anywhere on the row opens the detail
  // card, which shows the photo at full size.
  { key: 'photo_url',            label: 'Photo',                sortable: false, defaultVisible: true,
    render: (t) => (
      <img
        src={t.photo_url || PLACEHOLDER_IMG_SMALL}
        alt={t.name_en}
        className="w-9 h-9 rounded-full object-cover block bg-surface2"
        // kprofiles.com blocks hotlinks by Referer (returns 403); sending no
        // referer makes it serve the image. Harmless for Wikimedia photos.
        referrerPolicy="no-referrer"
        onError={onImgErrorSmall}
      />
    ) },
  { key: 'birth_year',           label: 'Age',                  sortable: true,  defaultVisible: true,
    render: (t) => t.birth_year ? CURRENT_YEAR - t.birth_year : '—' },
  { key: 'gender',                label: 'Gender',               sortable: true,  defaultVisible: true,
    render: (t) => t.gender || '—' },
  { key: 'occupation',            label: 'Profession',           sortable: false, defaultVisible: true, isArray: true,
    render: (t) => <TagPills values={t.occupation} /> },
  { key: 'debut_year',            label: 'Debut Year',           sortable: true,  defaultVisible: true,
    render: (t) => t.debut_year || '—' },
  // Key stays 'brand_names' though the cell now reads `brands`: column
  // visibility and order are persisted to localStorage by key, so renaming it
  // would quietly drop the column for anyone with saved preferences.
  // The table shows the 5-year window; the detail modal shows all 10.
  { key: 'brand_names',           label: 'Brands',                sortable: false, defaultVisible: true, isArray: true,
    render: (t) => (
      <BrandPills brands={brandsInWindow(t.brands)} limit={DECK_BRAND_LIMIT} />
    ) },
  { key: 'instagram_followers',   label: 'Instagram',            sortable: true,  defaultVisible: true,
    render: (t) => (
      <SocialCell
        handle={t.instagram_username}
        followers={t.instagram_followers}
        capturedAt={t.instagram_followers_captured_at}
        href={t.instagram_username ? `https://instagram.com/${t.instagram_username}` : undefined}
      />
    ) },

  // Default-hidden — opt-in via the column picker
  { key: 'nationality',           label: 'Nationality',          sortable: true,  defaultVisible: false,
    render: (t) => t.nationality || '—' },
  { key: 'group_name',            label: 'Group',                sortable: true,  defaultVisible: false,
    render: (t) => t.group_name || '—' },
  { key: 'id',                     label: 'ID',                   sortable: false, defaultVisible: false,
    render: (t) => <CopyIdCell id={t.id} /> },
  { key: 'active_countries',      label: 'Active Countries',     sortable: false, defaultVisible: false, isArray: true,
    render: (t) => <TagPills values={t.active_countries} /> },
  { key: 'other_names',           label: 'Other Names',          sortable: false, defaultVisible: false, isArray: true,
    render: (t) => <TagPills values={t.other_names} /> },
  { key: 'languages_spoken',      label: 'Languages Spoken',     sortable: false, defaultVisible: false, isArray: true,
    render: (t) => <TagPills values={t.languages_spoken} /> },
  { key: 'remarks',                label: 'Remarks',              sortable: false, defaultVisible: false,
    render: (t) => t.remarks || '—' },
  { key: 'youtube_followers',     label: 'YouTube',              sortable: true,  defaultVisible: false,
    render: (t) => <SocialCell handle={t.youtube_handle} followers={t.youtube_followers} capturedAt={t.youtube_followers_captured_at} /> },
  { key: 'twitter_followers',     label: 'Twitter',              sortable: true,  defaultVisible: false,
    render: (t) => <SocialCell handle={t.twitter_handle} followers={t.twitter_followers} capturedAt={t.twitter_followers_captured_at} /> },
  { key: 'xhs_followers',         label: 'XHS',                  sortable: true,  defaultVisible: false,
    render: (t) => <SocialCell handle={t.xhs_handle} followers={t.xhs_followers} capturedAt={t.xhs_followers_captured_at} /> },
  { key: 'douyin_followers',      label: 'Douyin',               sortable: true,  defaultVisible: false,
    render: (t) => <SocialCell handle={t.douyin_handle} followers={t.douyin_followers} capturedAt={t.douyin_followers_captured_at} /> },
  { key: 'weibo_followers',       label: 'Weibo',                sortable: true,  defaultVisible: false,
    render: (t) => <SocialCell handle={t.weibo_handle} followers={t.weibo_followers} capturedAt={t.weibo_followers_captured_at} /> },
]

export const DEFAULT_VISIBLE_COLUMNS = COLUMN_CONFIG.filter((c) => c.defaultVisible).map((c) => c.key)
export const DEFAULT_COLUMN_ORDER   = COLUMN_CONFIG.map((c) => c.key)

export interface ColumnGroup {
  label: string
  columns: ColumnDef[]
}

// The settings panel lays its checkboxes out in three themed columns rather
// than following COLUMN_CONFIG order. Groups are authored as ordered key
// lists so the panel's grouping can differ from the table's column order.
const COLUMN_GROUP_KEYS: { label: string; keys: (keyof TalentRow)[] }[] = [
  { label: 'Profile', keys: ['photo_url', 'birth_year', 'gender', 'nationality', 'languages_spoken', 'other_names', 'id'] },
  { label: 'Career',  keys: ['debut_year', 'group_name', 'occupation', 'brand_names', 'active_countries', 'remarks'] },
  { label: 'Social',  keys: ['instagram_followers', 'youtube_followers', 'twitter_followers', 'xhs_followers', 'douyin_followers', 'weibo_followers'] },
]

// Resolved groups for the picker. Locked columns are dropped (they aren't
// toggleable), and any non-locked column missing from every group is appended
// to the last one — so adding a column to COLUMN_CONFIG and forgetting the
// group list can't silently make it unreachable.
export const COLUMN_GROUPS: ColumnGroup[] = (() => {
  const groups = COLUMN_GROUP_KEYS.map(({ label, keys }) => ({
    label,
    columns: keys
      .map((key) => COLUMN_CONFIG.find((c) => c.key === key))
      .filter((c): c is ColumnDef => !!c && !c.locked),
  }))
  const placed  = new Set(groups.flatMap((g) => g.columns.map((c) => c.key)))
  const orphans = COLUMN_CONFIG.filter((c) => !c.locked && !placed.has(c.key))
  groups[groups.length - 1].columns.push(...orphans)
  return groups
})()
