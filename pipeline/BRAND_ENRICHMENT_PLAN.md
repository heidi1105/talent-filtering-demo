# Brand Affiliation — Work Breakdown

Planning doc produced 2026-08-02. Splits the brand-affiliation work into
separate chats so schema housekeeping stops colliding with pipeline design.

**Run the tracks in this order: A → C → B.** D and E can run alongside.
A goes first because part of its job is writing the decisions below into
`CLAUDE.md` — after that, every other chat inherits the context automatically
instead of you re-explaining it.

---

## Decisions already locked

Do not re-litigate these in the new chats. They're listed here so they can be
copied into `CLAUDE.md` in Track A.

| Question | Decision |
|---|---|
| What counts as an affiliation | Past **and** current contracts |
| Time window | Capture 10 years (2016+); display default 5 years, filtered in the view — not at ingest |
| Cap per talent | **None at ingest.** Store everything sourced; cap at display only |
| `not signed` status | Manual entry by the owner. AI output is constrained to `current` / `past` only |
| Date precision | `evidence_year smallint`, not a date — matches `birth_year` / `debut_year` convention |
| Year required? | Required for AI rows, optional for manual (enforced by CHECK on `extraction_method`) |
| Sub-brands | `Dior` and `Dior Beauty` stay **separate brand rows**. Aliases collapse language/casing only (`샤넬` → `Chanel`) |
| Unknown brand names | Auto-create, plus a per-run log of newly created brands for later merge review |
| Confidence rubric | **high** = named brand + explicit ambassador/endorsement wording + brand PR or major outlet · **medium** = one credible source, or affiliation implied not stated · **low** = fan site or aggregator only |
| Accuracy posture | Precision over recall. An empty cell beats a wrong one — this data reaches brands via the deck |
| Raw model output | Full response → per-run JSON log on disk (mirrors the followers pipeline). Small `raw jsonb` on the row for that affiliation's evidence only |
| Search language | Query Korean (`name_native`) as well as English — Korean endorsement news barely surfaces in English queries |
| No-wikidata talents (~100) | **Skipped** this run |

---

## Track A — Schema sync & documentation

**Do this first. It's small, and it unblocks the others.**

The `evidence_year` column and its CHECK constraint were applied directly in
Supabase, so the repo files have drifted from the live database. Until
`database.types.ts` is regenerated, TypeScript cannot see the new columns at
all, and the pipeline in Track C won't compile against them.

Scope:

- Append the applied statements to the "Incremental migrations" section at the
  bottom of `talent-filtering/schema.sql`
- Verify `brand_aliases` actually exists in Supabase — it was agreed but may not
  have been created
- Regenerate `lib/database.types.ts` (you run this; it needs your Supabase CLI)
- Write the decisions table above into `CLAUDE.md` (~line 81)
- Close the open question at `PRD.md:261`; update the stale `brand_affiliations
  text[]` reference at `PRD.md:96`
- Add a `changelog.md` entry (line 23 documents the old shape)

Three calls to make during this track:

1. **`schema.sql` exists in both repos and has already diverged** — the
   scrapping copy lacks the multi-platform view columns, the filtering copy
   lacks the inline `photo_source`. Recommend making `talent-filtering`
   canonical and deleting the other.
2. **Stale `talents_temp` table** is still live in Supabase with the v1 flat
   `brand_affiliations text[]` and `instagram_followers` typed as *string*. It
   pollutes every types regen. Drop it?
3. **Optional `parent_brand_id`** (nullable, self-referencing `brands`) — lets
   `Dior Beauty` point at `Dior` so "any Dior relationship" stays answerable.
   One-line ALTER now; the painful part later is backfilling parentage across
   hundreds of brands, not adding the column.

### Starting prompt

```
Schema sync task for the talent database.

I applied brand-affiliation columns directly in Supabase and the repo files
have drifted. The live talent_brands table now has: source_url, confidence,
extraction_method, extracted_at, evidence_year (smallint), plus a CHECK
constraint requiring evidence_year when extraction_method != 'manual'.

Please:
1. Check whether a brand_aliases table exists; if not, write the DDL
   (alias text primary key, brand_id uuid references brands on delete cascade).
2. Append all of the above to the "Incremental migrations" section at the
   bottom of schema.sql.
3. Update CLAUDE.md (~line 81), PRD.md (line 261 open question is now
   answered; line 96 still shows the v1 flat brand_affiliations), and
   changelog.md, using the decisions table in BRAND_ENRICHMENT_PLAN.md.
4. Tell me the exact command to regenerate lib/database.types.ts.

Also advise me on three things before changing anything:
- schema.sql exists in both talent-filtering and the main project and has
  diverged — should we make one canonical?
- the stale talents_temp table still in Supabase — drop it?
- adding a nullable parent_brand_id to brands — worth it now?

Confirm your plan with me before editing files.
```

---

## Track C — Brand enrichment pipeline

**The main build. Start after Track A so the types are current.**

Mirror the existing `enrichment/followers/` structure in `the main project` —
it's a good pattern already: pure logic separated from I/O, provider Protocol,
dry-run mode, per-batch commits, failure logs, unit tests.

Important difference to hold onto: followers is a deterministic lookup with
ground truth. Brand affiliation is open-ended web research with no
authoritative source, so the failure mode is silent and confident. Every
affiliation must carry a source URL and a year, or it doesn't get written.

Phases:

1. Scaffold `enrichment/brands/` — `run.py`, `provider_base.py`, `prompt.py`,
   `normalize.py`, `logs/`, tests
2. Brand-name normalization + alias resolution (do this on day one — retrofitting
   after thousands of rows is miserable). Include a `merge_brand(from_id, to_id)`
   helper: repoint `talent_brands`, delete the dupe, insert the old name as an alias
3. **Calibration gate** — 20 talents, hand-scored, before any spend at scale
4. Full run in batches, committed per batch, failures logged

For the calibration set: top 10 by Instagram followers as an A-list proxy, plus
10 random from the bottom half that still have a handle. Grading needs you to
know the right answer, so you approve the list — but you shouldn't have to
assemble it by hand. Validating only on A-list talent will report false accuracy;
the mid/obscure half is where fabrication shows up.

### Starting prompt

```
Build the brand-affiliation enrichment pipeline for the talent database.

Read BRAND_ENRICHMENT_PLAN.md in the talent-filtering folder first — the
decisions table there is settled, don't reopen it.

Model it on the existing enrichment/followers/ package in the main project:
same separation of pure logic from DB/network, provider Protocol, --dry-run
and --limit flags, per-batch commits, failure logs in logs/, unit tests.

Key difference: this is open-ended web research, not a deterministic lookup,
so it will hallucinate if allowed to. Every affiliation must have a source
URL and an evidence_year or it is not written. The prompt must explicitly
permit returning an empty list, and must search Korean name_native as well
as English.

Start with:
1. The package scaffold and the enrichment prompt design
2. Brand-name normalization + brand_aliases resolution, plus a
   merge_brand(from_id, to_id) helper
3. A calibration script that runs 20 talents and prints a scoreable report,
   including the distribution of affiliations found per talent
   (median / p90 / max / % with zero)

Propose the calibration set: top 10 by Instagram followers, 10 random from
the bottom half with a handle. Show it to me for approval.

Do not do a full production run until I've hand-scored the calibration output.
```

---

## Track B — Brand display (view + table + deck)

**Do this after Track C, once there's real data to look at.**

`talents_search` currently does `array_agg(b.name)` — a flat array of bare
names with no status and no confidence attached. That means
`lib/pptxExport.ts:200` structurally *cannot* render `"Chanel (current)"` or
gate the deck to high-confidence rows, which was the point of adding those
columns. Right now they're decorative.

Making them useful means the view aggregates objects rather than names, which
ripples into:

- `lib/supabaseClient.ts:18` — the `TalentRow` narrowing of `brand_names`
- `components/talent-table/columns.tsx:76` — the Brands cell (3 shown + N badge)
- `lib/pptxExport.ts:200,212` — the BRAND ASSOCIATION row

Also settled here: the deck's display cap (the table already answers 3 + overflow
per `PRD.md:134`), and whether the PPTX defaults to high-confidence rows only.

### Starting prompt

```
Update the brand display path in the talent database now that
talent_brands carries status, confidence, evidence_year and source_url.

Problem: talents_search aggregates array_agg(b.name), so the frontend and
the PPTX export only ever see bare brand names. They can't render
"Chanel (current)" or filter to high-confidence rows.

Please propose (don't apply yet) the change to make the view aggregate
brand objects instead of names, and walk me through the knock-on changes to:
- lib/supabaseClient.ts (TalentRow narrowing of brand_names)
- components/talent-table/columns.tsx line 76 (Brands cell)
- lib/pptxExport.ts lines 200 and 212 (BRAND ASSOCIATION row)

Two decisions I need to make with you:
- how many brands the deck cell should show before truncating, sorted
  current-first then past by evidence_year descending
- whether the PPTX should default to high-confidence affiliations only,
  with an override

Keep the 5-year display window filtered in the view, while the table stores 10.
```

---

## Track D — Group rows

**Small, separate pass. After Track C's individuals run.**

No schema change needed — `CLAUDE.md:78` already says a group is a talent row
with a null `birth_year`. You also don't need to source a group list; derive it
from what your roster already implies:

```sql
select distinct group_name from talents where group_name is not null;
```

Insert those as talent rows with `occupation = '{Group}'`, then run the same
enrichment. Two cautions: group rows will be sparse (no kprofiles photo or
socials), and running them separately keeps them out of your calibration numbers.

### Starting prompt

```
Add group rows to the talent database and run brand enrichment over them.

Groups need brand affiliations (e.g. NewJeans x Coca-Cola) but no group rows
exist yet. Per CLAUDE.md a group is just a talents row with a null birth_year
— no schema change needed.

1. Derive the group list from: select distinct group_name from talents
   where group_name is not null. Show me the list and the count first.
2. Insert them as talents rows with occupation = '{Group}' and null
   birth_year, idempotently (upsert on a stable key, per the pipeline rules).
3. Run the enrichment/brands pipeline over just those rows, as a separate
   pass from the individuals run.

Expect these rows to be sparse — no photo, no socials. Don't try to fill those.
```

---

## Deferred — not now, captured so they aren't lost

- **~100 talents with no Wikidata/Wikipedia** — run them through AI enrichment
  rather than hand-searching, accept partial results, timebox to a day. Add a
  per-record enrichment status so you never re-search the same dead ends.
  Hand-search only the ones the user actually asks for.
- **Works / filmography** — schema only this phase per `CLAUDE.md` constraint 7.
  No good free API covers Korean TV well; it's a real project, not an afternoon.
- **XHS / Weibo follower counts** — out of scope; Chinese socials are stored only
  when a source surfaces them.
- **Advanced filtering pop-up** — plan it after the team has used export a few
  times. Their real filter requests will beat your guesses.
- **Owner edit surface** — she needs to hand-edit `not signed` and a few other
  fields. Plan it together with the brand-alias merge UI; they want the same
  kind of screen.
