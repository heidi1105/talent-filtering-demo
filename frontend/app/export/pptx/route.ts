import { NextRequest, NextResponse } from 'next/server'
import { supabaseServer } from '@/lib/supabaseServerClient'
import { buildTalentDeck } from '@/lib/pptxExport'
import { asTalentRows, type BrandConfidence, type TalentRow } from '@/lib/supabaseClient'

// The deck is built into reference/pptx_template.pptx, which is read from disk
// at request time — so this route cannot run on the edge runtime.
export const runtime = 'nodejs'

// Only two floors are offered. 'low' is a fan-site/aggregator rating and has no
// business in a file that goes to a brand client, so it isn't reachable from
// the API at all rather than being merely discouraged.
const VALID_BRAND_CONFIDENCE: BrandConfidence[] = ['high', 'medium']

interface ExportPptxBody {
  talentIds?: string[]
  minBrandConfidence?: string
}

export async function POST(request: NextRequest) {
  // The service-role client below bypasses RLS, so without this check anyone
  // could POST talent IDs and download the data without signing in. The client
  // sends the Supabase session's access token; getUser() validates it with
  // Supabase rather than just decoding it.
  const token = request.headers.get('authorization')?.replace(/^Bearer\s+/i, '')
  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  const { data: authData, error: authError } = await supabaseServer.auth.getUser(token)
  if (authError || !authData.user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = (await request.json()) as ExportPptxBody
  const talentIds = body.talentIds ?? []

  if (talentIds.length === 0) {
    return NextResponse.json({ error: 'talentIds is required' }, { status: 400 })
  }

  // Anything unrecognised falls back to the strict floor, so a typo'd override
  // fails closed rather than quietly shipping medium-confidence affiliations.
  const minBrandConfidence: BrandConfidence =
    VALID_BRAND_CONFIDENCE.includes(body.minBrandConfidence as BrandConfidence)
      ? (body.minBrandConfidence as BrandConfidence)
      : 'high'

  const { data, error } = await supabaseServer
    .from('talents_search')
    .select('*')
    .in('id', talentIds)

  if (error || !data) {
    return NextResponse.json({ error: error?.message ?? 'Failed to fetch talents' }, { status: 500 })
  }

  // `.in()` does not preserve the order of `talentIds` — re-sort to match the
  // card order the user arranged on the export page, since that's what the
  // slide order is supposed to reflect.
  const byId = new Map(asTalentRows(data).map((t) => [t.id, t]))
  const ordered = talentIds
    .map((id) => byId.get(id))
    .filter((t): t is TalentRow => t != null)

  const buffer = await buildTalentDeck(ordered, minBrandConfidence)

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      'Content-Type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'Content-Disposition': 'attachment; filename="talents.pptx"',
    },
  })
}
