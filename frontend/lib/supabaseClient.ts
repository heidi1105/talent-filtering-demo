import { createClient } from '@supabase/supabase-js'
import type { Database } from './database.types'

export const supabase = createClient<Database>(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

export type TalentSearchRow = Database['public']['Views']['talents_search']['Row']

export type BrandConfidence = 'high' | 'medium' | 'low'

// One entry of the `brands` jsonb the view builds with jsonb_build_object.
// confidence is nullable because talent_brands has no NOT NULL on it;
// evidence_year is null only on manual rows (see the CHECK there). `status`
// exists on talent_brands but is deliberately not in the view payload — see
// the comment on the aggregate in schema.sql.
export interface TalentBrand {
  name:              string
  confidence:        BrandConfidence | null
  evidence_year:     number | null
  extraction_method: 'ai' | 'manual' | null
  source_url:        string | null
}

// Supabase's type generator marks every view column nullable, since views
// carry no constraints of their own. `id` and `name_en` are NOT NULL on the
// underlying `talents` table, and `brand_names` is coalesced to '{}' in the
// view — all three are safe to narrow back to non-null here, once.
//
// `brands` is Omit'd rather than intersected like the others: it's jsonb, so
// the generator types it as the catch-all `Json`, and `Json & TalentBrand[]`
// collapses to something unusable (unlike `(string[] | null) & string[]`,
// which resolves cleanly). Omit also keeps this compiling before the
// regenerated types land, since Omit tolerates a key the source lacks.
// The shape is guaranteed by jsonb_build_object in the view, so this is an
// assertion, not a validation boundary — if those keys change, change these.
export type TalentRow = Omit<TalentSearchRow, 'brands'> & {
  id:          string
  name_en:     string
  brand_names: string[]
  brands:      TalentBrand[]
}

/** Narrows raw `talents_search` rows to TalentRow. The generator types `brands`
 *  as the catch-all `Json`, which TypeScript won't let you assert straight to
 *  TalentBrand[] — the two don't overlap enough for a single cast. Routing every
 *  read through here keeps that step-through-unknown written down once, next to
 *  the reasoning above, instead of repeated at each call site. */
export function asTalentRows(rows: TalentSearchRow[] | null): TalentRow[] {
  return (rows ?? []) as unknown as TalentRow[]
}
