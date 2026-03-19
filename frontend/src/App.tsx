import { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from './lib/auth'
import ActiveScreen from './screens/ActiveScreen'
import CommitmentsScreen from './screens/CommitmentsScreen'
import OnboardingTour from './components/OnboardingTour'
import Review from './screens/Review'
import Log from './screens/Log'
import CommitmentDetail from './screens/CommitmentDetail'
import LoginScreen from './screens/LoginScreen'
import SignUpScreen from './screens/SignUpScreen'
import ForgotPasswordScreen from './screens/ForgotPasswordScreen'
import ResetPasswordScreen from './screens/ResetPasswordScreen'
import OnboardingScreen from './screens/OnboardingScreen'
import OnboardingIdentityScreen from './screens/OnboardingIdentityScreen'
import AccountSettingsScreen from './screens/settings/AccountSettingsScreen'
import IntegrationsSettingsScreen from './screens/settings/IntegrationsSettingsScreen'
import IdentitySettingsScreen from './screens/settings/IdentitySettingsScreen'
import PrototypeDashboard from './screens/PrototypeDashboard'
import AdminScreen from './screens/AdminScreen'
import { getIdentityStatus } from './api/identity'
import { listSources } from './api/sources'

const SNOOZE_KEY = 'identity_onboarding_snoozed_until'

function isIdentitySnoozed(): boolean {
  const val = localStorage.getItem(SNOOZE_KEY)
  if (!val) return false
  return Date.now() < new Date(val).getTime()
}

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center">Loading…</div>
  if (!session) return <Navigate to="/login" replace />
  return <>{children}</>
}

/**
 * Wraps the main dashboard and redirects to /onboarding/identity
 * if the user has no confirmed identity profiles.
 */
function IdentityGuard({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['identity-status'],
    queryFn: getIdentityStatus,
    staleTime: 60_000,
    retry: 1,
  })
  const { data: sources, isLoading: sourcesLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: listSources,
    staleTime: 60_000,
    retry: 1,
  })

  const isLoading = statusLoading || sourcesLoading

  useEffect(() => {
    if (isLoading) return
    if (isIdentitySnoozed()) return
    const hasSources = sources && sources.length > 0
    if (!hasSources) return // No integrations yet — nothing to reconcile
    if (status && !status.has_confirmed_identities) {
      navigate('/onboarding/identity', { replace: true })
    }
  }, [isLoading, status, sources, navigate])

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="w-8 h-8 border-2 border-black border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return <>{children}</>
}

type Tab = 'active' | 'commitments'

function AuthenticatedApp() {
  const [activeTab, setActiveTab] = useState<Tab>('active')

  if (activeTab === 'commitments') {
    return (
      <>
        <CommitmentsScreen activeTab={activeTab} onTabChange={setActiveTab} />
        <OnboardingTour />
      </>
    )
  }
  return (
    <>
      <ActiveScreen activeTab={activeTab} onTabChange={setActiveTab} />
      <OnboardingTour />
    </>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginScreen />} />
      <Route path="/signup" element={<SignUpScreen />} />
      <Route path="/forgot-password" element={<ForgotPasswordScreen />} />
      <Route path="/reset-password" element={<ResetPasswordScreen />} />
      <Route
        path="/onboarding"
        element={
          <AuthGuard>
            <OnboardingScreen />
          </AuthGuard>
        }
      />
      <Route
        path="/onboarding/identity"
        element={
          <AuthGuard>
            <OnboardingIdentityScreen />
          </AuthGuard>
        }
      />
      <Route
        path="/"
        element={
          <AuthGuard>
            <IdentityGuard>
              <AuthenticatedApp />
            </IdentityGuard>
          </AuthGuard>
        }
      />
      <Route
        path="/source/:sourceType"
        element={
          <AuthGuard>
            <Review />
          </AuthGuard>
        }
      />
      <Route
        path="/source/:sourceType/log"
        element={
          <AuthGuard>
            <Log />
          </AuthGuard>
        }
      />
      <Route
        path="/commitment/:id"
        element={
          <AuthGuard>
            <CommitmentDetail />
          </AuthGuard>
        }
      />
      <Route
        path="/settings/sources"
        element={<Navigate to="/settings/integrations" replace />}
      />
      <Route
        path="/settings/account"
        element={
          <AuthGuard>
            <AccountSettingsScreen />
          </AuthGuard>
        }
      />
      <Route
        path="/settings/integrations"
        element={
          <AuthGuard>
            <IntegrationsSettingsScreen />
          </AuthGuard>
        }
      />
      <Route
        path="/settings/identity"
        element={
          <AuthGuard>
            <IdentitySettingsWrapper />
          </AuthGuard>
        }
      />
      <Route path="/prototype" element={<PrototypeDashboard />} />
      <Route
        path="/admin"
        element={
          <AuthGuard>
            <AdminScreen />
          </AuthGuard>
        }
      />
    </Routes>
  )
}

/** Wrapper to give IdentitySettingsScreen the standard settings page layout. */
function IdentitySettingsWrapper() {
  return (
    <div className="min-h-screen bg-white pb-12">
      <div className="px-4 pt-8 pb-4">
        <a href="/" className="text-sm text-gray-500 hover:text-black transition-colors">
          ← Back
        </a>
        <h1 className="text-2xl font-bold text-black mt-3">Identity settings</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage the names and emails Rippled uses to match commitments to you.
        </p>
      </div>
      <div className="px-4">
        <IdentitySettingsScreen />
      </div>
    </div>
  )
}
