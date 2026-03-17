import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { AuthGate } from './components/AuthGate'
import { Layout } from './components/Layout'
import { HealthPage } from './pages/HealthPage'
import { CommitmentsPage } from './pages/CommitmentsPage'
import { CandidatesPage } from './pages/CandidatesPage'
import { EventsPage } from './pages/EventsPage'
import { SurfacingPage } from './pages/SurfacingPage'
import { DigestsPage } from './pages/DigestsPage'
import { PipelinePage } from './pages/PipelinePage'

export default function App() {
  return (
    <AuthGate>
      <Layout>
        <Routes>
          <Route path="/" element={<HealthPage />} />
          <Route path="/commitments" element={<CommitmentsPage />} />
          <Route path="/candidates" element={<CandidatesPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/surfacing" element={<SurfacingPage />} />
          <Route path="/digests" element={<DigestsPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
        </Routes>
      </Layout>
    </AuthGate>
  )
}
