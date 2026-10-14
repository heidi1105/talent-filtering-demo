# Enrichment Protocol — Combined Data + Brand Enrichment

## Overview

Automated batch enrichment of Korean talent data for an internal
talent database. Each scheduled run processes one batch of talents from the seed
file, researching missing biographical data and brand affiliations via web search.
Results are saved to JSON files for human review before database loading.

**Do NOT update the database directly.** All results go to JSON files.

---

## File Locations

All paths relative to the project root

| File | Purpose |
|---|---|
| `seed/wikidata_raw_cleaned.json` | Source: original talent records (batches 0-58) |
| `enrichment/combined/new_group_talents.json` | Source: 740 new group-affiliated talents (batches 59+) |
| `enrichment/combined/progress.json` | Tracks which batch to process next |
| `enrichment/combined/results/batch_NNN.json` | Enrichment output per batch |
| `enrichment/combined/flagged.json` | Talents with suspicious/conflicting data |

---

## Step-by-Step Run Procedure

### 1. Connect and read progress

Read `enrichment/combined/progress.json`:

```json
{
  "batch_size": 500,
  "next_batch": 0,
  "total_talents": 5867,
  "completed_batches": [],
  "last_run_at": null,
  "status": "ready"
}
```

If `next_batch * batch_size >= total_talents`, all enrichment is done — report
completion and stop. If `status` is `"paused"`, stop and report.

### 2. Load the batch

Check `progress.json` for `new_group_talents` — if present and `next_batch >= new_group_talents.start_batch`, read from the alternate source file instead:

```python
import json

with open('enrichment/combined/progress.json') as f:
    progress = json.load(f)

ngt = progress.get("new_group_talents")
if ngt and progress["next_batch"] >= ngt["start_batch"]:
    # New group talents (batches 59+)
    with open(ngt["source_file"]) as f:
        all_talents = json.load(f)
    offset_batch = progress["next_batch"] - ngt["start_batch"]
    start = offset_batch * progress["batch_size"]
    end = min(start + progress["batch_size"], len(all_talents))
    batch = all_talents[start:end]
else:
    # Original talents (batches 0-58)
    with open('seed/wikidata_raw_cleaned.json') as f:
        all_talents = json.load(f)
    start = progress["next_batch"] * progress["batch_size"]
    end = min(start + progress["batch_size"], len(all_talents))
    batch = all_talents[start:end]
```

### 3. Process each talent

For every talent in the batch, do the following research.

#### 3a. Determine what's missing

Check which fields are null/empty: `debut_year`, `birth_year`, `name_native`,
`photo_url`, `other_names`, `languages_spoken`, `instagram`, `twitter`, `youtube`,
`nationality`, `active_countries`.

**Nationality and active_countries rules:**
- `nationality` = place of birth / origin, simplified. Use country adjective form:
  "South Korea" → "Korean", "United States" → "American", "Thailand" → "Thai", etc.
- `active_countries` = where they perform, have shows, release music, act in dramas.
  A Korean-born person working in Hollywood: nationality = "Korean",
  active_countries = ["United States"]. LISA from BLACKPINK: nationality = "Thai",
  active_countries = ["South Korea"]. Most talents will be nationality = "Korean",
  active_countries = ["South Korea"], which is the default — only record if different.

#### 3b. Data enrichment — fill missing fields

Use WebSearch and WebFetch to find missing data. **Strategy per talent:**

1. **Try Wikipedia first** — construct a search query:
   - `"[name_en]" "[name_native]" Wikipedia Korean [occupation]`
   - If a Wikipedia URL appears in results, use WebFetch to extract structured data
   
2. **Try MyDramaList** if actor/actress and gaps remain:
   - `"[name_en]" site:mydramalist.com`

3. **Try IMDB** if gaps remain:
   - `"[name_en]" Korean site:imdb.com`

**Extract these fields from sources:**
- `debut_year` — "Years active" on Wikipedia, or earliest credit on MDL/IMDB
- `birth_year` — from infobox/bio (only if currently missing)
- `name_native` — Korean name (한글) from Wikipedia title or infobox
- `photo_url` — Wikimedia Commons image URL (from Wikipedia infobox)
- `other_names` — alternative names, birth name, stage name variations
- `languages_spoken` — from Wikipedia if listed
- `instagram` / `twitter` / `youtube` — from Wikipedia external links or official sources ONLY

**Trusted sources:** Wikipedia, MyDramaList, IMDB, official social media profiles,
Soompi, AllKPop, Naver Entertainment.

**Do NOT trust:** Fan wikis (kprofiles user content, namuwiki), fan social accounts,
Pinterest, random blogs.

If the talent already has data for a field, keep the existing value UNLESS the new
data clearly corrects a factual error.

#### 3c. Brand enrichment

Search for brand/commercial endorsements:
- `"[name_en]" brand ambassador endorsement 2024 OR 2025 OR 2026`
- `"[name_native]" 브랜드 앰버서더` (if name_native exists)

**What counts as a brand affiliation:**
- Brand ambassador, spokesperson, face of campaign, official endorsement, contract
- Both CURRENT and PAST relationships (2016 onward)

**Does NOT count:** wearing a brand in photos with no reported deal, drama/film
roles, fan speculation, one-off event attendance.

**For each brand found, record:**
- `brand_name` — exact name from the source (keep sub-brands separate: "Dior" ≠ "Dior Beauty")
- `source_url` — the actual URL where you found this
- `evidence_year` — year of the article/announcement (must be 2016+)
- `confidence` — "high" (brand PR/major outlet + explicit wording), "medium" (one
  credible source or implied), "low" (fan site only)
- `evidence_note` — one sentence on what the source says

**Do NOT include `status` (current/past)** — it is not accurate enough and is not
displayed in the app.

**PRECISION OVER RECALL:** An empty list is better than a wrong entry. This data
is used directly in exported presentations. If you're not confident, leave it out.

#### 3d. Flag suspicious results

Add the talent to `flagged.json` if ANY of these apply:
- Search results seem to be about a different person with the same name
- Birth year conflicts between sources (>1 year difference from existing data)
- The person appears to not be in the entertainment industry at all
- Very little information exists online (possible non-notable person)
- Any data that "looks wrong" — trust your judgment

**Do NOT flag** talents just because they work outside Korea. Instead, set their
`nationality` and `active_countries` correctly in the enriched data. For example,
a Korean-born Hollywood actress gets nationality = "Korean", active_countries =
["United States"] — that's valid data, not a flag.

### 4. Save results

#### Result format per talent:
```json
{
  "wikidata_id": "Q12345",
  "name_en": "Original English Name",
  "name_native_original": "Original native name or null",
  "enriched": {
    "debut_year": 2007,
    "name_native": "김수현",
    "photo_url": "https://upload.wikimedia.org/...",
    "other_names": ["Kim Su-hyeon", "수현"],
    "languages_spoken": ["Korean", "English"],
    "instagram": "soohyun_k216"
  },
  "brands": [
    {
      "brand_name": "Samsung Galaxy",
      "source_url": "https://www.soompi.com/article/...",
      "evidence_year": 2024,
      "confidence": "high",
      "evidence_note": "Named Samsung Galaxy global ambassador in Jan 2024"
    }
  ],
  "brands_searched": true,
  "sources_consulted": ["https://en.wikipedia.org/wiki/Kim_Soo-hyun"],
  "flagged": false,
  "flag_reason": null,
  "searched_at": "2026-08-31T12:00:00Z"
}
```

**Only include fields in `enriched` where you found NEW data not already in the
source record.** If you found nothing new, `enriched` should be `{}`. If no brands
found, `brands` should be `[]`. Both outcomes are normal and expected.

**IMPORTANT:** Always set `"brands_searched": true` on every talent result, even
when no brands are found. This tells the database loader to set `brands_checked_at`
so we never re-search the same talent. A talent with `brands: []` and
`brands_searched: true` is a completed result, not an incomplete one.

#### Checkpointing:
- After every 10 talents, write the accumulated results so far to
  `results/batch_NNN.json` (overwriting the previous checkpoint for this batch)
- After completing the full batch, write the final version and update `progress.json`
- This ensures no more than 10 talents of work is lost on any failure

#### Flagged file format (`flagged.json`):
```json
[
  {
    "wikidata_id": "Q12345",
    "name_en": "Name",
    "flag_reason": "Birth year conflict: Wikipedia says 1990, existing data says 1992",
    "batch": 0,
    "flagged_at": "2026-08-31T12:00:00Z"
  }
]
```

Read the existing flagged.json first and append new entries. Create it if it
doesn't exist.

### 5. Update progress

After the batch completes, update `progress.json`:
- Increment `next_batch`
- Add the batch number to `completed_batches`
- Set `last_run_at` to the current ISO timestamp
- Keep `status` as `"ready"`

### 6. Report

Print a summary:
- Batch number and range (e.g., "Batch 0: talents 0–499")
- How many talents had new data found
- How many brand affiliations found
- How many flagged
- Next batch number and estimated remaining batches

---

## Efficiency Tips

- **Wikipedia first**: Most data can be found on one Wikipedia page. If Wikipedia
  has everything, skip MyDramaList/IMDB searches.
- **Skip searches for complete records**: If a talent already has all fields
  populated, only do brand searches.
- **Batch reads**: Load the full talent batch from JSON in one device_bash call,
  don't read one at a time.
- **Groups**: For group entities (birth_year is null, the talent IS the group),
  research the group's brand deals but don't try to find individual biographical data.

---

## Notes

- The ~342 talents already brand-enriched via the Python pipeline should still get
  data enrichment. Skip brand research for those (note it in the result).
- Social media handles: only record if from Wikipedia external links or the
  official verified account. Never from fan accounts.
- Photo URLs: prefer Wikimedia Commons URLs (stable). Avoid hotlinking news sites.
- `evidence_year` for brands must be 2016 or later.
- When in doubt, leave a field empty rather than guess.

---

## Post-enrichment: Apply corrections to seed files

After all batches complete, run the apply script to merge enriched biographical
data back into the seed files:

```bash
python 05_apply_enrichment.py --dry-run   # preview
python 05_apply_enrichment.py             # apply
```

This reads all `batch_*.json` results, extracts the `enriched` dicts, and merges
corrections into `wikidata_raw_cleaned.json` and regenerates `talents_seed.json`.
Only fills empty fields by default; use `--force` to overwrite existing values.

Then load into the database:

```bash
python 03a_load_cleaned.py --force        # load talent data
python 04_load_combined_brands.py         # load brand affiliations
```
