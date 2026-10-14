// Style tokens for the exported deck, shared between the server-side builder
// and the on-screen preview cards.
//
// Every value here is derived from reference/pptx_template.pptx itself — the
// "Neutral" theme and slide master in that file — rather than chosen. The
// deck is assembled *into* that template (see lib/pptxTemplate.ts), so the
// table has to sit on the template's palette or it reads as pasted on.
// Lives apart from pptxExport.ts, which pulls in server-only deps
// (pptxgenjs / image-size / node:fs) the export page must not bundle.

export interface DeckTokens {
  slideBg: string
  surface: string
  text: string
  muted: string
  border: string
  accent: string
  headingFont: string
  bodyFont: string
  /** Row-label headings (NAME, AGE, OCCUPATION, …). */
  headingColor: string
  headingBold: boolean
}

// Derivations from ppt/theme/theme1.xml and ppt/slideMasters/slideMaster1.xml:
//
//   text     dk1 = 1F2937, the template's body/title ink
//   muted    dk1 at tint 75% -> 575E69; the exact treatment the master gives
//            its own "Page N" text, so secondary text matches the furniture
//   border   accent4 9CA3AF with lumMod 20% / lumOff 80% -> ECEDF0; the same
//            derivation the master applies to its frame rectangle's line
//   accent   theme hlink = 1D4ED8, so the Instagram links match PowerPoint's
//            own link color for this theme instead of introducing a new one
//   fonts    major and minor latin are both Aptos
//
// The slide background is not painted by us at all — the master owns it
// (white, plus the frame). `slideBg` exists only so the preview
// canvas on the export page can stand the cards on the same ground.
export const DECK_TOKENS: DeckTokens = {
  slideBg: 'FFFFFF',
  surface: 'FFFFFF',
  text: '1F2937',
  muted: '575E69',
  border: 'ECEDF0',
  accent: '1D4ED8',
  headingFont: 'Aptos',
  bodyFont: 'Aptos',
  headingColor: '1F2937',
  // Labels stay regular weight — matching the table as it was built against
  // the reference talent deck, where the column labels are unbolded.
  headingBold: false,
}

// How many talents PptxGenJS lays out per slide — the on-screen export grid
// mirrors this with a "Slide N" divider so card order maps visibly to deck order.
export const TALENTS_PER_SLIDE = 4

// `DeckTokens` colors are plain hex without '#' (PptxGenJS's convention) — this
// converts one for use in inline CSS.
export function hex(token: string): string {
  return `#${token}`
}
