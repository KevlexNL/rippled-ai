import React, { createContext, useContext, useEffect, useState } from 'react'
import type { Session, User } from '@supabase/supabase-js'
import { supabase } from './supabase'
import { apiGet } from './apiClient'

interface AuthContextValue {
  session: Session | null
  user: User | null
  loading: boolean
  signOut: () => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  checkOnboardingComplete: () => Promise<boolean>
}

const AuthContext = createContext<AuthContextValue>({
  session: null,
  user: null,
  loading: true,
  signOut: async () => {},
  signUp: async () => {},
  checkOnboardingComplete: async () => false,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signOut = async () => {
    await supabase.auth.signOut()
    setSession(null)
  }

  const signUp = async (email: string, password: string): Promise<void> => {
    // Explicitly pass emailRedirectTo so confirmation links always point
    // to the current origin — not whatever Supabase has as Site URL.
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: window.location.origin,
      },
    })
    if (error) throw error
  }

  const checkOnboardingComplete = async (): Promise<boolean> => {
    try {
      const data = await apiGet<{ has_sources: boolean }>('/api/v1/sources/onboarding-status')
      return data.has_sources
    } catch {
      // If API fails, also check user metadata
      const { data: { user } } = await supabase.auth.getUser()
      return user?.user_metadata?.onboarding_complete === true
    }
  }

  return (
    <AuthContext.Provider value={{ session, user: session?.user ?? null, loading, signOut, signUp, checkOnboardingComplete }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="w-8 h-8 border-2 border-black border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!session) {
    // Render nothing here — App.tsx handles redirect via Navigate
    return null
  }

  return <>{children}</>
}
