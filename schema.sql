-- ============================================================
-- Talent Database Schema — v3 (synced from live Supabase 2026-08-05)
-- Source of truth: Supabase production database.
-- Korean talents. Normalized. Brands populated, Works schema only.
-- ============================================================

create extension if not exists pg_trgm;

-- ============================================================
-- Core entity: a talent. A group (e.g. STAYC) is simply a row with a
-- null birth_year — no special handling.
-- ============================================================
create table if not exists talents (
  id                uuid primary key default gen_random_uuid(),

  -- Identity
  name_en           text not null,
  name_native       text,
  birth_year        smallint,            -- age = current_year - birth_year; null for groups
  gender            text check (gender in ('Male', 'Female', 'Other')),
  nationality       text,                -- REAL nationality. No default.
  wikidata_id       text unique,         -- e.g. "Q123456"; unique, null when unknown
  other_names       text[] default '{}', -- aliases: stage name, romanizations, native variants
  languages_spoken  text[] default '{}', -- e.g. ['Korean','Mandarin','English']

  -- Career
  occupation        text[] default '{}', -- controlled vocab incl. Dancer, Rapper, MC, etc.
  active_countries  text[] default '{}', -- markets where active: KR, CN, HK, TH, JP ...
  group_name        text,                -- the group an individual belongs to (null otherwise)
  debut_year        smallint,            -- leading 4-digit year from Wikipedia "Years active"; null if unknown

  -- Media
  photo_url         text,                -- linked, never hosted (in the app/DB)
  photo_source      text                 -- provenance of photo_url
                      check (photo_source in ('wikidata', 'kprofiles', 'manual')),

  -- Misc
  remarks           text,                -- notes, updated by users manually if necessary

  -- Pipeline timestamps
  brands_checked_at timestamptz,         -- set by enrichment/brands/run.py after each talent is researched (even if 0 affiliations found)

  -- Metadata
  source            text,                -- 'manual', 'mydramalist', 'wikipedia', ...
  last_updated      timestamptz default now(),
  created_at        timestamptz default now()
);

-- ============================================================
-- Social accounts — one row per platform per talent.
-- Latest-snapshot follower model (no history table in Phase 1).
-- ============================================================
create table if not exists social_accounts (
  id                    uuid primary key default gen_random_uuid(),
  talent_id             uuid not null references talents(id) on delete cascade,
  platform              text not null
                          check (platform in ('instagram','youtube','twitter','xhs','douyin','weibo')),
  handle                text,            -- stored without leading @
  profile_url           text,
  follower_count        bigint,          -- numeric for sort/filter; humanize for display ("2.1m")
  followers_captured_at timestamptz,     -- when the snapshot was taken
  last_updated          timestamptz default now(),
  unique (talent_id, platform)
);

-- ============================================================
-- Works (drama / movie / album) — SCHEMA NOW, POPULATE LATER.
-- ============================================================
create table if not exists works (
  id          uuid primary key default gen_random_uuid(),
  title       text not null,
  type        text check (type in ('drama','movie','album')),
  year        smallint,
  created_at  timestamptz default now()
);

create table if not exists talent_works (
  talent_id   uuid not null references talents(id) on delete cascade,
  work_id     uuid not null references works(id) on delete cascade,
  role        text,                       -- 'Lead', 'Supporting', 'Title track', ...
  primary key (talent_id, work_id)
);

-- ============================================================
-- Brands — normalized. Names dedupe; campaign metadata attaches here.
-- ============================================================
create table if not exists brands (
  id          uuid primary key default gen_random_uuid(),
  name        text not null unique,
  created_at  timestamptz default now()
);

create table if not exists talent_brands (
  talent_id          uuid not null references talents(id) on delete cascade,
  brand_id           uuid not null references brands(id) on delete cascade,
  status             text,                -- 'current','past','not signed'
  source_url         text,                -- provenance URL for this affiliation
  confidence         text                 -- 'high','medium','low'
                       check (confidence in ('high', 'medium', 'low')),
  evidence_year      smallint,            -- year affiliation was evidenced; matches birth_year/debut_year convention
  extraction_method  text                 -- 'ai' or 'manual'
                       check (extraction_method in ('ai', 'manual')),
  extracted_at       timestamptz default now(),
  raw                jsonb,               -- per-affiliation evidence from AI enrichment
  primary key (talent_id, brand_id),
  -- AI rows must have an evidence_year; manual rows may omit it
  constraint talent_brands_evidence_year_check
    check (extraction_method = 'manual' or evidence_year is not null)
);

-- ============================================================
-- Brand aliases — resolves language/casing/punctuation variants
-- to one brand row. e.g. '샤넬' → Chanel.
-- ============================================================
create table if not exists brand_aliases (
  alias       text primary key,           -- normalized: '샤넬', 'chanel beauty', 'CHANEL'
  brand_id    uuid not null references brands(id) on delete cascade
);

-- ============================================================
-- Read view: flattens the common fields so the frontend queries,
-- filters, and sorts against ONE relation. Storage stays normalized.
-- ============================================================
drop view if exists talents_search;
create view talents_search as
with brand_rows as (
  select
    tb.talent_id,
    b.name  as name,
    tb.confidence,
    tb.evidence_year,
    tb.extraction_method,
    tb.source_url
  from talent_brands tb
  join brands b on b.id = tb.brand_id
  -- Storage bound: the pipeline captures 10 years (2016+). Repeated here so a
  -- manually entered older deal can't silently widen what the UI shows.
  -- Manual rows may have a null evidence_year (talent_brands_evidence_year_check
  -- only requires one for AI rows) — without the second arm they'd compare
  -- NULL >= cutoff, come back false, and vanish with no trace.
  where tb.evidence_year >= extract(year from now())::int - 10
     or (tb.extraction_method = 'manual' and tb.evidence_year is null)
)
select
  t.*,
  -- Search-only helper: other_names is text[], and PostgREST/.or() can't ilike
  -- an array column directly. Flattened to text here so the client can match
  -- keywords against it the same way it does name_en/name_native/group_name.
  array_to_string(t.other_names, ' ')                 as other_names_text,
  case
    when t.birth_year is not null
    then (extract(year from now())::int - t.birth_year)
    else null
  end                                                  as age,
  ig.handle                                            as instagram_username,
  ig.follower_count                                    as instagram_followers,
  ig.followers_captured_at                             as instagram_followers_captured_at,
  yt.handle                                            as youtube_handle,
  yt.follower_count                                    as youtube_followers,
  yt.followers_captured_at                             as youtube_followers_captured_at,
  tw.handle                                            as twitter_handle,
  tw.follower_count                                    as twitter_followers,
  tw.followers_captured_at                             as twitter_followers_captured_at,
  xhs.handle                                           as xhs_handle,
  xhs.follower_count                                   as xhs_followers,
  xhs.followers_captured_at                            as xhs_followers_captured_at,
  dy.handle                                            as douyin_handle,
  dy.follower_count                                    as douyin_followers,
  dy.followers_captured_at                             as douyin_followers_captured_at,
  wb.handle                                            as weibo_handle,
  wb.follower_count                                    as weibo_followers,
  wb.followers_captured_at                             as weibo_followers_captured_at,
  -- FILTER + facet target, narrowed to the 5-year display window. Windowed
  -- here rather than in the client so .overlaps('brand_names', …) stays a
  -- server-side row filter.
  coalesce(
    array_agg(distinct br.name) filter (
      where br.name is not null
        and (br.evidence_year >= extract(year from now())::int - 5
             or (br.extraction_method = 'manual' and br.evidence_year is null))
    ),
    '{}'
  )                                                    as brand_names,

  -- DISPLAY payload: the full 10-year set, newest evidence first. The detail
  -- modal renders all of it; the table cell and the PPTX deck narrow it to 5
  -- years via brandsInWindow()/brandsForDeck() in lib/talentDisplay.ts.
  -- Ordering lives here so those three consumers can't each invent their own —
  -- jsonb preserves array order (it only reorders object keys), so it survives
  -- intact to the client.
  --
  -- `status` is deliberately absent: dropped from the display path by decision
  -- 2026-08-12 — brands now render unlabelled, so a past deal is
  -- indistinguishable from a live one, and a 'not signed' row (still writable
  -- on the base table) counts here as an ordinary affiliation. Nothing in this
  -- view consults status any more.
  -- source_url is included so the detail modal can link each affiliation to its
  -- evidence. It measures ~79 chars at the median and adds ~1% to the export
  -- handoff payload — not the thing that makes that URL too long.
  coalesce(
    jsonb_agg(
      jsonb_build_object(
        'name',              br.name,
        'confidence',        br.confidence,
        'evidence_year',     br.evidence_year,
        'extraction_method', br.extraction_method,
        'source_url',        br.source_url
      )
      order by
        br.evidence_year desc nulls last,
        br.name
    ) filter (where br.name is not null),
    '[]'::jsonb
  )                                                    as brands
from talents t
left join social_accounts ig
       on ig.talent_id = t.id and ig.platform = 'instagram'
left join social_accounts yt
       on yt.talent_id = t.id and yt.platform = 'youtube'
left join social_accounts tw
       on tw.talent_id = t.id and tw.platform = 'twitter'
left join social_accounts xhs
       on xhs.talent_id = t.id and xhs.platform = 'xhs'
left join social_accounts dy
       on dy.talent_id = t.id and dy.platform = 'douyin'
left join social_accounts wb
       on wb.talent_id = t.id and wb.platform = 'weibo'
left join brand_rows br on br.talent_id = t.id
group by t.id, ig.handle, ig.follower_count, ig.followers_captured_at,
         yt.handle, yt.follower_count, yt.followers_captured_at,
         tw.handle, tw.follower_count, tw.followers_captured_at,
         xhs.handle, xhs.follower_count, xhs.followers_captured_at,
         dy.handle, dy.follower_count, dy.followers_captured_at,
         wb.handle, wb.follower_count, wb.followers_captured_at;

-- ============================================================
-- Indexes
-- ============================================================
-- Name search (full-text + trigram partial match)
create index if not exists talents_name_fts
  on talents using gin (to_tsvector('simple'::regconfig, coalesce(name_en,'') || ' ' || coalesce(name_native,'')));
create index if not exists talents_name_trgm
  on talents using gin (name_en gin_trgm_ops);
create index if not exists talents_other_names_trgm
  on talents using gin (other_names);
create index if not exists talents_wikidata_idx      on talents (wikidata_id);

-- Filters / sorts
create index if not exists talents_gender_idx           on talents (gender);
create index if not exists talents_nationality_idx      on talents (nationality);
create index if not exists talents_occupation_idx       on talents using gin (occupation);
create index if not exists talents_active_countries_idx on talents using gin (active_countries);
create index if not exists talents_birth_year_idx       on talents (birth_year);
create index if not exists talents_group_idx            on talents (group_name);
create index if not exists talents_debut_year_idx       on talents (debut_year);
create index if not exists talents_photo_source_idx     on talents (photo_source);
create index if not exists talents_languages_spoken_trgm on talents using gin (languages_spoken);

-- Joins / lookups
create index if not exists social_accounts_talent_idx        on social_accounts (talent_id);
create index if not exists social_accounts_platform_foll_idx on social_accounts (platform, follower_count);
create index if not exists talent_works_work_idx             on talent_works (work_id);
create index if not exists talent_brands_brand_idx           on talent_brands (brand_id);

-- ============================================================
-- RLS: enabled. Access is invite-only.
--   * Signed-in (authenticated) users can read; anon gets nothing.
--   * The pipeline (direct DB connection) and the export route (service key)
--     bypass RLS by design, so neither needs a policy.
--   * Supabase dashboard: turn OFF "Allow new users to sign up" and invite
--     users by email. The app signs in with magic links only.
-- ============================================================
do $$
declare t text;
begin
  foreach t in array array[
    'talents','social_accounts','works','talent_works',
    'brands','talent_brands','brand_aliases'
  ] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists "authenticated read" on %I', t);
    execute format('create policy "authenticated read" on %I for select to authenticated using (true)', t);
  end loop;
end $$;

-- Views run with the owner's rights by default, which would bypass RLS.
-- security_invoker makes the view obey the caller's policies instead.
alter view talents_search set (security_invoker = true);
