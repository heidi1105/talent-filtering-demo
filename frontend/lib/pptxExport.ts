import PptxGenJS from 'pptxgenjs'
import { imageSize } from 'image-size'
import type { BrandConfidence, TalentRow } from './supabaseClient'
import { brandDeckCell, humanizeFollowers } from './talentDisplay'
import { DECK_TOKENS, TALENTS_PER_SLIDE, type DeckTokens } from './deckStyle'
import { graftSlidesIntoTemplate } from './pptxTemplate'

// Geometry (inches) derived from the reference talent deck the layout was designed against.
const SLIDE_W = 13.333
const SLIDE_H = 7.5
const TABLE_X = 0.698, TABLE_Y = 1.246
const LABEL_COL_W = 1.559
const DATA_COL_W = 2.594
// Portrait box (~3:4) — a sample of real talent photos skews portrait (headshots), so this
// crops far less than a square box did. Sizing is 'contain' (see below), so nothing is ever
// cropped regardless of the source photo's own ratio; this just picks the box shape that
// needs the least letterboxing for the common case.
const PHOTO_W = 1.8
const PHOTO_H = 2.4
const PHOTO_Y = TABLE_Y + 0.07
// PHOTO (no label), NAME, AGE, OCCUPATION, INSTAGRAM, BRAND, REMARKS — minimums, PowerPoint auto-grows.
const ROW_HEIGHTS = [2.55, 0.4, 0.267, 0.267, 0.267, 0.149, 0.149]
// Goes into the title placeholder the template layout already defines, rather
// than a text box of our own — so position, size and type styling are the
// template's. The slide number is likewise the master's "Page N" placeholder,
// and the slide background, frame and page number all come from the master. See
// lib/pptxTemplate.ts.
const DECK_TITLE = 'TALENTS'

interface PhotoAsset {
  dataUri: string
  width: number
  height: number
}

const PHOTO_FETCH_ATTEMPTS = 3
const PHOTO_FETCH_TIMEOUT_MS = 8_000
// Wikimedia (the source of most photo_urls — see CLAUDE.md's Wikipedia coverage note) throttles
// or deprioritizes requests with no identifying User-Agent, especially concurrent anonymous ones.
// See https://meta.wikimedia.org/wiki/User-Agent_policy
const PHOTO_FETCH_USER_AGENT = 'TalentFilteringDemo/1.0 (export tool; https://github.com/heidi1105/talent-filtering-demo)'

async function fetchPhotoOnce(url: string): Promise<PhotoAsset | null> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), PHOTO_FETCH_TIMEOUT_MS)
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { 'User-Agent': PHOTO_FETCH_USER_AGENT, Accept: 'image/*' },
    })
    if (!res.ok) {
      console.warn(`[pptxExport] photo fetch got HTTP ${res.status} for ${url}`)
      return null
    }
    const bytes = new Uint8Array(await res.arrayBuffer())
    const { width, height } = imageSize(bytes)
    if (!width || !height) {
      console.warn(`[pptxExport] photo fetch returned unreadable image dimensions for ${url}`)
      return null
    }
    const contentType = res.headers.get('content-type') || 'image/jpeg'
    return {
      dataUri: `data:${contentType};base64,${Buffer.from(bytes).toString('base64')}`,
      width,
      height,
    }
  } catch (err) {
    console.warn(`[pptxExport] photo fetch failed for ${url}:`, err)
    return null
  } finally {
    clearTimeout(timer)
  }
}

async function fetchPhoto(url: string | null): Promise<PhotoAsset | null> {
  if (!url) return null
  for (let attempt = 1; attempt <= PHOTO_FETCH_ATTEMPTS; attempt++) {
    const photo = await fetchPhotoOnce(url)
    if (photo) return photo
    if (attempt < PHOTO_FETCH_ATTEMPTS) {
      await new Promise((resolve) => setTimeout(resolve, attempt * 500))
    }
  }
  console.warn(`[pptxExport] giving up on photo after ${PHOTO_FETCH_ATTEMPTS} attempts: ${url}`)
  return null
}

// pptxgenjs (Node) can't probe real image dimensions, so `sizing: { type: 'contain' | 'cover' }`
// only computes correct crop/letterbox math if we hand it the true width/height ourselves
// via the image's top-level w/h. Its internal unit heuristic treats any value >=100 as
// already-EMU and <100 as inches — either way the *ratio* between w and h survives, as long
// as both land on the same side of that boundary. Scale up so real (tiny) images can't
// straddle it.
function normalizeForRatio(width: number, height: number): [number, number] {
  const smaller = Math.min(width, height)
  const factor = smaller < 100 ? 1000 / smaller : 1
  return [width * factor, height * factor]
}

function photoX(colIndex: number): number {
  return TABLE_X + LABEL_COL_W + colIndex * DATA_COL_W + (DATA_COL_W - PHOTO_W) / 2
}

function chunk<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = []
  for (let i = 0; i < items.length; i += size) chunks.push(items.slice(i, i + size))
  return chunks
}

function talentTableRows(
  talents: (TalentRow | null)[],
  theme: DeckTokens,
  minConfidence: BrandConfidence,
): PptxGenJS.TableRow[] {
  const labelCell = (label: string, valign: PptxGenJS.VAlign = 'top'): PptxGenJS.TableCell => ({
    text: label,
    options: {
      bold: theme.headingBold, align: 'right', valign, color: theme.headingColor,
      fontFace: theme.headingFont, fontSize: 12, fill: { color: theme.surface },
    },
  })

  const dataCell = (
    content: string | PptxGenJS.TableCell[],
    valign: PptxGenJS.VAlign = 'top',
    align: PptxGenJS.HAlign = 'center',
  ): PptxGenJS.TableCell => ({
    text: content,
    options: {
      align, valign, color: theme.text, fontFace: theme.bodyFont, fontSize: 12,
      fill: { color: theme.surface },
    },
  })

  const nameCell = (t: TalentRow | null): PptxGenJS.TableCell => {
    if (!t) return dataCell('')
    const runs: PptxGenJS.TableCell[] = [
      { text: t.name_en, options: { bold: true, color: theme.text, breakLine: true } },
    ]
    if (t.name_native) {
      runs.push({ text: t.name_native, options: { fontSize: 10, color: theme.muted } })
    }
    return dataCell(runs)
  }

  const ageCell = (t: TalentRow | null): PptxGenJS.TableCell =>
    dataCell(t?.age != null ? String(t.age) : '')

  const occupationCell = (t: TalentRow | null): PptxGenJS.TableCell =>
    dataCell(!t ? '' : (t.occupation && t.occupation.length > 0 ? t.occupation.join(', ') : '—'))

  const instagramCell = (t: TalentRow | null): PptxGenJS.TableCell => {
    if (!t || !t.instagram_username) return dataCell(!t ? '' : '—')
    const followers = t.instagram_followers
    const runs: PptxGenJS.TableCell[] = [
      {
        text: `@${t.instagram_username}`,
        options: {
          color: theme.accent, breakLine: true,
          hyperlink: { url: `https://instagram.com/${t.instagram_username}` },
        },
      },
    ]
    if (followers != null) {
      runs.push({ text: `(${humanizeFollowers(followers).toLowerCase()} followers)`, options: { fontSize: 10, color: theme.muted } })
    }
    return dataCell(runs)
  }

  // Already ordered by the view (newest evidence first), so this filters and
  // truncates but never re-sorts. Affiliations render as a name plus its grey
  // evidence year — no status label, so nothing here distinguishes a past deal
  // from a live one beyond how old the year is. The year trails the name on the
  // same line rather than taking its own: three brands each needing two lines
  // costs ~0.57in of row growth, which eats most of the slack ROW_HEIGHTS
  // leaves before the footer.
  const brandCell = (t: TalentRow | null): PptxGenJS.TableCell => {
    if (!t) return dataCell('')
    const { lines, overflow } = brandDeckCell(t.brands, minConfidence)
    if (lines.length === 0) return dataCell('N/A')

    const runs: PptxGenJS.TableCell[] = []
    lines.forEach(({ name, year }, i) => {
      // breakLine on the final run emits a trailing empty line, which grows
      // the row and pushes the table toward the footer for no visible gain.
      const endsLine = i < lines.length - 1 || overflow > 0
      runs.push({
        text: name,
        options: { breakLine: year == null && endsLine, color: theme.text },
      })
      if (year != null) {
        runs.push({
          text: ` ${year}`,
          options: { breakLine: endsLine, fontSize: 10, color: theme.muted },
        })
      }
    })
    if (overflow > 0) {
      runs.push({ text: `+${overflow} more`, options: { fontSize: 10, color: theme.muted } })
    }
    return dataCell(runs)
  }

  const remarksCell = (): PptxGenJS.TableCell => dataCell('')

  return [
    // No label — this row exists purely to reserve space for the photo overlay.
    [labelCell(''), ...talents.map(() => dataCell(''))],
    [labelCell('NAME'), ...talents.map(nameCell)],
    [labelCell('AGE'), ...talents.map(ageCell)],
    [labelCell('OCCUPATION'), ...talents.map(occupationCell)],
    [labelCell('INSTAGRAM'), ...talents.map(instagramCell)],
    [labelCell('BRAND ASSOCIATION'), ...talents.map(brandCell)],
    [labelCell('REMARKS'), ...talents.map(remarksCell)],
  ]
}

export async function buildTalentDeck(
  talents: TalentRow[],
  // Defaults to 'high' so an omitted argument can never widen what reaches a
  // client deck — loosening it has to be a deliberate act at the call site.
  minBrandConfidence: BrandConfidence = 'high',
): Promise<Buffer> {
  const tokens = DECK_TOKENS
  const pptx = new PptxGenJS()
  pptx.defineLayout({ name: 'TALENT_DECK', width: SLIDE_W, height: SLIDE_H })
  pptx.layout = 'TALENT_DECK'

  const slideGroups = chunk(talents, TALENTS_PER_SLIDE)

  for (const group of slideGroups) {
    // No background, title or footer drawn here — the template's slide master
    // supplies all three once these slides are grafted into it.
    const slide = pptx.addSlide()

    const padded: (TalentRow | null)[] = [...group, ...Array(TALENTS_PER_SLIDE - group.length).fill(null)]

    slide.addTable(talentTableRows(padded, tokens, minBrandConfidence), {
      x: TABLE_X, y: TABLE_Y,
      colW: [LABEL_COL_W, DATA_COL_W, DATA_COL_W, DATA_COL_W, DATA_COL_W],
      rowH: ROW_HEIGHTS,
      border: { type: 'solid', color: tokens.border, pt: 1 },
      autoPage: false,
    })

    const photos = await Promise.all(group.map((t) => fetchPhoto(t.photo_url)))
    group.forEach((_, colIndex) => {
      const x = photoX(colIndex)
      // Background box first — guarantees a clean, theme-matched fill behind any
      // letterbox/pillarbox padding 'contain' leaves for photos that aren't ~3:4.
      slide.addShape('roundRect', {
        x, y: PHOTO_Y, w: PHOTO_W, h: PHOTO_H,
        fill: { color: tokens.surface }, line: { type: 'none' }, rectRadius: 0.03,
      })
      const photo = photos[colIndex]
      if (photo) {
        const [natW, natH] = normalizeForRatio(photo.width, photo.height)
        slide.addImage({
          data: photo.dataUri, x, y: PHOTO_Y, w: natW, h: natH,
          sizing: { type: 'contain', w: PHOTO_W, h: PHOTO_H },
        })
      }
    })
  }

  // These slides are only an intermediate: PptxGenJS can't open an existing
  // file, so the talent slides are rendered into a throwaway presentation and
  // then transplanted into the deck template, which is the package
  // that actually gets returned.
  const generated = await pptx.write({ outputType: 'nodebuffer' })
  return graftSlidesIntoTemplate(Buffer.from(generated as Uint8Array), { slideTitle: DECK_TITLE })
}
