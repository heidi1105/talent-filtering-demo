import { readFile } from 'node:fs/promises'
import path from 'node:path'
import JSZip from 'jszip'

// Grafts PptxGenJS-generated slides into the deck template package.
//
// PptxGenJS cannot open an existing .pptx — it only writes new ones from
// scratch. So the deck is assembled in two passes: pptxExport.ts renders the
// talent slides into a throwaway presentation, and this module transplants
// just those slides (plus the media and hyperlinks they reference) into
// reference/pptx_template.pptx, which stays the base package.
//
// Everything that gives the deck its look — slide master, the six layouts, the
// theme, the frame rectangle, the cover slide — is the template's own bytes, untouched. We only append parts.

// Read from reference/ rather than a copy kept beside the code: the owner
// updates the template in place, and a second copy would drift out of date
// without anything failing loudly.
const TEMPLATE_PATH = path.join(process.cwd(), 'reference', 'pptx_template.pptx')

// The layout every generated slide is attached to: "2_Title and Content", the
// same one the template's own cover slide uses. Its title placeholder is where
// the deck title lands (see TITLE_PLACEHOLDER_SP).
const TARGET_LAYOUT = 'slideLayout3.xml'

const RELS_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
const REL_TYPE_IMAGE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image'
const REL_TYPE_LAYOUT = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout'
const REL_TYPE_SLIDE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide'
const REL_TYPE_NOTES_SLIDE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide'
const CONTENT_TYPE_SLIDE = 'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'

// Content types for image extensions PptxGenJS may emit. The template already
// declares png/jpeg defaults; anything else has to be added or PowerPoint
// rejects the package.
const IMAGE_CONTENT_TYPES: Record<string, string> = {
  png: 'image/png',
  jpeg: 'image/jpeg',
  jpg: 'image/jpeg',
  gif: 'image/gif',
  svg: 'image/svg+xml',
  webp: 'image/webp',
  bmp: 'image/bmp',
  tiff: 'image/tiff',
}

// JSZip writes an entry for each intermediate directory by default. OPC
// packages produced by PowerPoint contain no directory entries, and a stricter
// reader can balk at ones it has no content type for, so every write below
// passes this.
const ZIP_WRITE: JSZip.JSZipFileOptions = { createFolders: false }

interface Rel {
  id: string
  type: string
  target: string
  targetMode?: string
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function parseRels(xml: string): Rel[] {
  const rels: Rel[] = []
  for (const match of xml.matchAll(/<Relationship\b[^>]*\/>/g)) {
    const tag = match[0]
    const attr = (name: string) => tag.match(new RegExp(`${name}="([^"]*)"`))?.[1]
    const id = attr('Id')
    const type = attr('Type')
    const target = attr('Target')
    if (!id || !type || !target) continue
    rels.push({ id, type, target, targetMode: attr('TargetMode') })
  }
  return rels
}

function serializeRels(rels: Rel[]): string {
  const entries = rels
    .map((rel) => {
      const mode = rel.targetMode ? ` TargetMode="${escapeXml(rel.targetMode)}"` : ''
      return `<Relationship Id="${escapeXml(rel.id)}" Type="${escapeXml(rel.type)}" Target="${escapeXml(rel.target)}"${mode}/>`
    })
    .join('')
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n<Relationships xmlns="${RELS_NS}">${entries}</Relationships>`
}

// Highest numeric suffix already used by parts matching e.g. ppt/media/imageN.png,
// so appended parts never collide with the template's own.
function maxPartIndex(zip: JSZip, prefix: string): number {
  let max = 0
  const pattern = new RegExp(`^${prefix}(\\d+)\\.`)
  zip.forEach((relativePath) => {
    const found = relativePath.match(pattern)
    if (found) max = Math.max(max, Number(found[1]))
  })
  return max
}

function maxRelId(rels: Rel[]): number {
  return rels.reduce((max, rel) => {
    const n = Number(rel.id.replace(/^rId/, ''))
    return Number.isFinite(n) ? Math.max(max, n) : max
  }, 0)
}

// The title placeholder shape. Carrying no <a:xfrm> is deliberate: position,
// size, font and color are all inherited from the layout, which is the whole
// point of going through the template rather than drawing our own text box.
function titlePlaceholderSp(shapeId: number, title: string): string {
  return (
    `<p:sp><p:nvSpPr><p:cNvPr id="${shapeId}" name="Title ${shapeId}"/>` +
    `<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>` +
    `<p:spPr/><p:txBody><a:bodyPr><a:normAutofit/></a:bodyPr><a:lstStyle/>` +
    `<a:p><a:r><a:rPr lang="en-US" b="1" dirty="0"/><a:t>${escapeXml(title)}</a:t></a:r></a:p>` +
    `</p:txBody></p:sp>`
  )
}

// The "Page ‹#›" placeholder, copied from slideLayout3. PowerPoint only renders
// a slide number if the placeholder exists on the slide itself — inheriting it
// from the layout is not enough — so each generated slide gets its own copy.
// The <a:fld> is what makes the number live; the literal text inside it is only
// the fallback a renderer shows before it evaluates the field.
function slideNumberPlaceholderSp(shapeId: number, slideNumber: number): string {
  return (
    `<p:sp><p:nvSpPr><p:cNvPr id="${shapeId}" name="Slide Number Placeholder ${shapeId}"/>` +
    `<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>` +
    `<p:nvPr><p:ph type="sldNum" sz="quarter" idx="4"/></p:nvPr></p:nvSpPr>` +
    `<p:spPr><a:xfrm><a:off x="10824963" y="6492875"/><a:ext cx="1001094" cy="222192"/></a:xfrm>` +
    `<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>` +
    `<p:txBody><a:bodyPr vert="horz" lIns="91440" tIns="45720" rIns="91440" bIns="45720" rtlCol="0" anchor="ctr"/>` +
    `<a:lstStyle/><a:p><a:pPr algn="l"/>` +
    `<a:r><a:rPr lang="en-US" dirty="0"/><a:t>Page </a:t></a:r>` +
    `<a:fld id="{172400D1-27C7-4544-B969-DB100EEC5A68}" type="slidenum">` +
    `<a:rPr lang="en-US" smtClean="0"/><a:pPr algn="l"/><a:t>${slideNumber}</a:t></a:fld>` +
    `<a:endParaRPr lang="en-US" sz="900" dirty="0"/></a:p></p:txBody></p:sp>`
  )
}

// Shape ids must be unique within a slide's spTree. PptxGenJS numbers its own
// shapes from 1, so the injected placeholders start well clear of them.
const INJECTED_SHAPE_ID_BASE = 900

function prepareSlideXml(xml: string, slideNumber: number, title: string): string {
  // PptxGenJS writes an explicit white <p:bg> onto every slide. Left in place it
  // would paint over the master's background, hiding the frame rectangle and
  // any branding the template carries on its master.
  let out = xml.replace(/<p:bg>[\s\S]*?<\/p:bg>/, '')

  const injected =
    titlePlaceholderSp(INJECTED_SHAPE_ID_BASE, title) +
    slideNumberPlaceholderSp(INJECTED_SHAPE_ID_BASE + 1, slideNumber)

  const closeIndex = out.lastIndexOf('</p:spTree>')
  if (closeIndex === -1) throw new Error('Generated slide XML has no <p:spTree> to inject into')
  out = out.slice(0, closeIndex) + injected + out.slice(closeIndex)

  return out
}

function addContentTypeOverrides(xml: string, slidePaths: string[], extensions: Set<string>): string {
  let out = xml

  for (const ext of extensions) {
    if (new RegExp(`<Default Extension="${ext}"`, 'i').test(out)) continue
    const contentType = IMAGE_CONTENT_TYPES[ext]
    if (!contentType) continue
    out = out.replace(/(<Types\b[^>]*>)/, `$1<Default Extension="${ext}" ContentType="${contentType}"/>`)
  }

  const overrides = slidePaths
    .map((p) => `<Override PartName="/${p}" ContentType="${CONTENT_TYPE_SLIDE}"/>`)
    .join('')
  return out.replace('</Types>', `${overrides}</Types>`)
}

// docProps/app.xml carries a slide count and a parallel vector of slide titles.
// PowerPoint tolerates staleness here, but a count that disagrees with the
// package is exactly the kind of thing that makes a file "need repair" in
// stricter readers, so both are kept honest.
function updateAppProps(xml: string, addedTitles: string[]): string {
  if (addedTitles.length === 0) return xml

  const slideCount = Number(xml.match(/<Slides>(\d+)<\/Slides>/)?.[1] ?? 0)
  let out = xml.replace(/<Slides>\d+<\/Slides>/, `<Slides>${slideCount + addedTitles.length}</Slides>`)

  // "Slide Titles" is one of the HeadingPairs entries; its <vt:i4> counts how
  // many of the TitlesOfParts entries are slide titles (the rest are fonts and
  // themes). Both it and the vector size have to grow together.
  out = out.replace(
    /(<vt:lpstr>Slide Titles<\/vt:lpstr><\/vt:variant><vt:variant><vt:i4>)(\d+)(<\/vt:i4>)/,
    (_m, before: string, count: string, after: string) =>
      `${before}${Number(count) + addedTitles.length}${after}`,
  )

  out = out.replace(
    /(<TitlesOfParts><vt:vector size=")(\d+)(" baseType="lpstr">)([\s\S]*?)(<\/vt:vector><\/TitlesOfParts>)/,
    (_m, open: string, size: string, mid: string, body: string, close: string) => {
      const added = addedTitles.map((t) => `<vt:lpstr>${escapeXml(t)}</vt:lpstr>`).join('')
      return `${open}${Number(size) + addedTitles.length}${mid}${body}${added}${close}`
    },
  )

  return out
}

export interface GraftOptions {
  /** Text placed in each generated slide's inherited title placeholder. */
  slideTitle: string
}

/**
 * Takes a PptxGenJS-produced .pptx, lifts its slides out, and appends them to
 * the deck template — after the template's own cover slide, in order.
 * Returns the merged package.
 */
export async function graftSlidesIntoTemplate(
  generated: Buffer,
  { slideTitle }: GraftOptions,
): Promise<Buffer> {
  const [templateBytes, source] = await Promise.all([
    readFile(TEMPLATE_PATH),
    JSZip.loadAsync(generated),
  ])
  const target = await JSZip.loadAsync(templateBytes)

  // Generated slides in their own order — slide1, slide2, … — which is the
  // talent order the export page arranged.
  const sourceSlides = Object.keys(source.files)
    .filter((name) => /^ppt\/slides\/slide\d+\.xml$/.test(name))
    .sort((a, b) => Number(a.match(/(\d+)\.xml$/)![1]) - Number(b.match(/(\d+)\.xml$/)![1]))

  if (sourceSlides.length === 0) throw new Error('Generated deck contains no slides')

  const presRelsPath = 'ppt/_rels/presentation.xml.rels'
  const presRelsXml = await target.file(presRelsPath)!.async('string')
  const presRels = parseRels(presRelsXml)

  let nextRelId = maxRelId(presRels) + 1
  let nextSlideIndex = maxPartIndex(target, 'ppt/slides/slide') + 1
  let nextMediaIndex = maxPartIndex(target, 'ppt/media/image') + 1

  const newSlidePaths: string[] = []
  const newSlideRelIds: string[] = []
  const mediaExtensions = new Set<string>()

  for (const sourcePath of sourceSlides) {
    const slidePath = `ppt/slides/slide${nextSlideIndex}.xml`
    const sourceRelsPath = sourcePath.replace(/slides\/(slide\d+\.xml)$/, 'slides/_rels/$1.rels')

    // Slide number as the reader will see it: the template's existing slides
    // come first, then these.
    const slideNumber = nextSlideIndex
    const slideXml = prepareSlideXml(
      await source.file(sourcePath)!.async('string'),
      slideNumber,
      slideTitle,
    )

    // Rewrite the slide's relationships in place rather than the slide XML:
    // r:id values stay exactly as PptxGenJS wrote them, so the drawing markup
    // needs no rewriting at all — only what each id points at changes.
    const sourceRels = parseRels(await source.file(sourceRelsPath)!.async('string'))
    const rewritten: Rel[] = []

    for (const rel of sourceRels) {
      if (rel.type === REL_TYPE_LAYOUT) {
        rewritten.push({ ...rel, target: `../slideLayouts/${TARGET_LAYOUT}` })
        continue
      }

      if (rel.type === REL_TYPE_IMAGE && rel.targetMode !== 'External') {
        const sourceMediaPath = path.posix.normalize(path.posix.join('ppt/slides', rel.target))
        const ext = (sourceMediaPath.split('.').pop() ?? 'png').toLowerCase()
        const mediaPath = `ppt/media/image${nextMediaIndex}.${ext}`
        nextMediaIndex += 1
        mediaExtensions.add(ext)
        target.file(mediaPath, await source.file(sourceMediaPath)!.async('uint8array'), ZIP_WRITE)
        rewritten.push({ ...rel, target: `../media/${path.posix.basename(mediaPath)}` })
        continue
      }

      // PptxGenJS attaches an (empty) notes slide to everything it renders.
      // Those parts are deliberately not copied — the deck has no speaker
      // notes — so the relationship has to go too, or it dangles and
      // PowerPoint declares the file in need of repair.
      if (rel.type === REL_TYPE_NOTES_SLIDE) continue

      // Everything else — notably the external hyperlink rels behind the
      // Instagram handles — carries over untouched.
      rewritten.push(rel)
    }

    target.file(slidePath, slideXml, ZIP_WRITE)
    target.file(`ppt/slides/_rels/slide${nextSlideIndex}.xml.rels`, serializeRels(rewritten), ZIP_WRITE)

    const relId = `rId${nextRelId}`
    nextRelId += 1
    presRels.push({ id: relId, type: REL_TYPE_SLIDE, target: `slides/slide${nextSlideIndex}.xml` })
    newSlidePaths.push(slidePath)
    newSlideRelIds.push(relId)
    nextSlideIndex += 1
  }

  target.file(presRelsPath, serializeRels(presRels), ZIP_WRITE)

  // Slide order lives in <p:sldIdLst>, not in the rel ids — appending here is
  // what actually puts the talent slides after the cover.
  const presPath = 'ppt/presentation.xml'
  const presXml = await target.file(presPath)!.async('string')
  const existingSldIds = [...presXml.matchAll(/<p:sldId id="(\d+)"/g)].map((m) => Number(m[1]))
  // Per the schema, slide ids start at 256 and must be unique.
  let nextSldId = Math.max(255, ...existingSldIds) + 1
  const appended = newSlideRelIds
    .map((relId) => `<p:sldId id="${nextSldId++}" r:id="${relId}"/>`)
    .join('')
  target.file(presPath, presXml.replace('</p:sldIdLst>', `${appended}</p:sldIdLst>`), ZIP_WRITE)

  const contentTypesPath = '[Content_Types].xml'
  const contentTypesXml = await target.file(contentTypesPath)!.async('string')
  target.file(contentTypesPath, addContentTypeOverrides(contentTypesXml, newSlidePaths, mediaExtensions), ZIP_WRITE)

  const appPropsPath = 'docProps/app.xml'
  const appPropsFile = target.file(appPropsPath)
  if (appPropsFile) {
    const appXml = await appPropsFile.async('string')
    target.file(appPropsPath, updateAppProps(appXml, newSlidePaths.map(() => slideTitle)), ZIP_WRITE)
  }

  const merged = await target.generateAsync({
    type: 'nodebuffer',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 },
    mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  })

  return Buffer.from(merged)
}
