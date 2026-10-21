'use client'

/**
 * app/login/page.tsx
 *
 * WHY THIS EXISTS:
 * The only public route. Unauthenticated users land here when
 * page.tsx detects no session and redirects.
 *
 * HOW IT WORKS:
 * - User types their email and clicks "Send magic link"
 * - supabase.auth.signInWithOtp() emails them a signed link
 * - Clicking that link redirects back to the app origin
 * - Supabase JS client picks up the token from the URL hash,
 *   stores the session in localStorage, fires onAuthStateChange
 * - AuthProvider updates → user is now logged in → page.tsx renders
 *
 * SECURITY NOTE:
 * Sign-ups are disabled and shouldCreateUser is false, so a link is only
 * sent to invited emails; anyone else gets an error and no email.
 * Known trade-off: this reveals whether an email is on the invite list
 * (email enumeration). Accepted for a small internal tool in exchange
 * for clear feedback to real users.
 */

import { useState } from 'react'
import { supabase } from '@/lib/supabaseClient'

type Status = 'idle' | 'sending' | 'sent' | 'error' | 'rate-limited'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<Status>('idle')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus('sending')

    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        // window.location.origin = http://localhost:3000 in dev,
        // your Vercel URL in production. Both must be whitelisted in:
        // Supabase → Authentication → URL Configuration → Redirect URLs
        emailRedirectTo: window.location.origin,
        // Required when "Allow new users to sign up" is disabled in Supabase.
        // Without this, signInWithOtp tries to create a new user, which
        // fails when signup is off. Setting false means: only send the link
        // if this email already exists as an invited/confirmed user.
        shouldCreateUser: false,
      },
    })

    if (error) {
      // 429 = rate limited — too many OTP emails sent in a short window.
      // Supabase free tier allows ~3 per hour per email address.
      setStatus(error.status === 429 ? 'rate-limited' : 'error')
    } else {
      setStatus('sent')
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="bg-surface border border-border rounded p-8 w-full max-w-sm">
        <h1 className="text-text text-xl font-semibold mb-1">Talent Roster</h1>
        <p className="text-muted text-sm mb-6">
          Enter your email to receive a sign-in link.
        </p>

        {status === 'sent' ? (
          <p className="text-accent text-sm">
            Check your email for the sign-in link.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="bg-surface2 border border-border text-text text-sm rounded px-3 py-2 placeholder:text-dim focus:outline-none focus:border-border2"
            />
            <button
              type="submit"
              disabled={status === 'sending'}
              className="bg-accent text-bg text-sm font-medium rounded px-3 py-2 hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {status === 'sending' ? 'Sending…' : 'Send magic link'}
            </button>
            {status === 'error' && (
              <p className="text-red-400 text-sm">
                Something went wrong. Try again.
              </p>
            )}
            {status === 'rate-limited' && (
              <p className="text-red-400 text-sm">
                Too many requests. Please wait a few minutes and try again.
              </p>
            )}
          </form>
        )}
      </div>
    </div>
  )
}
