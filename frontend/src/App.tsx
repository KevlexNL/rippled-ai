import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './lib/auth'
import Dashboard from './screens/Dashboard'
import Review from './screens/Review'
import Log from './screens/Log'
import CommitmentDetail from './screens/CommitmentDetail'
import LoginScreen from './screens/LoginScreen'

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center">Loading…</div>
  if (!session) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginScreen />} />
      <Route
        path="/"
        element={
          <AuthGuard>
            <Dashboard />
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
    </Routes>
  )
}
