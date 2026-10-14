'use client'

/**
 * AuthProvider.tsx
 *
 * WHY THIS EXISTS:
 * Supabase manages auth state (tokens, sessions) but every component
 * that needs "is the user logged in?" would have to call Supabase
 * directly. This provider does it once at the top of the tree and
 * shares the answer via React Context.
 *
 * HOW IT WORKS:
 * 1. On mount, getSession() checks localStorage for an existing session
 *    (stored by the Supabase JS client after a magic link click).
 * 2. onAuthStateChange fires on login, logout, and token refresh —
 *    keeping state in sync without polling.
 * 3. useAuth() exposes { user, loading, signOut } to any child component.
 *
 * INTERVIEW NOTES:
 * - Standard React Context + Provider pattern for cross-tree state sharing.
 * - onAuthStateChange is Supabase's equivalent of Firebase's onAuthStateChanged.
 * - The cleanup (unsubscribe) in useEffect prevents memory leaks on unmount.
 */

import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '@/lib/supabaseClient'
import type { User } from '@supabase/supabase-js'

interface AuthContextType {
  user: User | null
  loading: boolean
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true) // true until first session check completes

  useEffect(() => {
    // 1. Check if there's already a session in localStorage
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // 2. Listen for future auth changes (login, logout, token refresh)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
    })

    // 3. Clean up the listener when the component unmounts
    return () => subscription.unsubscribe()
  }, [])

  const signOut = async () => {
    await supabase.auth.signOut()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

/**
 * useAuth() — call this in any component that needs the current user.
 *
 * Usage:
 *   const { user, loading, signOut } = useAuth()
 *   if (loading) return <Spinner />
 *   if (!user) return null // redirect handled in page.tsx
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
