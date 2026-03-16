import { useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './lib/auth'
import ActiveScreen from './screens/ActiveScreen'
import CommitmentsScreen from './screens/CommitmentsScreen'
import Review from './screens/Review'
import Log from './screens/Log'
import CommitmentDetail from './screens/CommitmentDetail'
import LoginScreen from './screens/LoginScreen'
import SignUpScreen from './screens/SignUpScreen'
import ForgotPasswordScreen from './screens/ForgotPasswordScreen'
import ResetPasswordScreen from './screens/ResetPasswordScreen'
import OnboardingScreen from './screens/OnboardingScreen'
import SourcesSettingsScreen from './screens/settings/SourcesSettingsScreen'
import AccountSettingsScreen from './screens/settings/AccountSettingsScreen'
import IntegrationsSettingsScreen from './screens/settings/IntegrationsSettingsScreen'
import PrototypeDashboard from './screens/PrototypeDashboard'

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center">Loading…</div>
  if (!session) return <Navigate to="/login" replace />
  return <>{children}</>
}

type Tab = 'active' | 'commitments'

function AuthenticatedApp() {
  const [activeTab, setActiveTab] = useState<Tab>('active')

  if (activeTab === 'commitments') {
    return <CommitmentsScreen activeTab={activeTab} onTabChange={setActiveTab} />
  }
  return <ActiveScreen activeTab={activeTab} onTabChange={setActiveTab} />
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
        path="/"
        element={
          <AuthGuard>
            <AuthenticatedApp />
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
        element={
          <AuthGuard>
            <SourcesSettingsScreen />
          </AuthGuard>
        }
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
      <Route path="/prototype" element={<PrototypeDashboard />} />
    </Routes>
  )
}
