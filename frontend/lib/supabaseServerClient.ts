import { createClient } from '@supabase/supabase-js'
import type { Database } from './database.types'

// Service-role client for server-only code (Route Handlers). Never import this
// from a client component — SUPABASE_SERVICE_KEY must never reach the browser bundle.
export const supabaseServer = createClient<Database>(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!
)
