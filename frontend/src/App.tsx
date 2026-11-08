import { Route, Routes } from 'react-router-dom'
import { AppShell } from './layout/AppShell'
import { DiscoveryPage } from './pages/DiscoveryPage'
import { JobDetailPage } from './pages/JobDetailPage'
import { JobsPage } from './pages/JobsPage'
import { Placeholder } from './pages/Placeholder'
import { ResumePage } from './pages/ResumePage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Placeholder title="Dashboard" next="Job and application activity will appear here." />} />
        <Route path="resume" element={<ResumePage />} />
        <Route path="discovery" element={<DiscoveryPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/:jobId" element={<JobDetailPage />} />
        <Route path="tailoring" element={<Placeholder title="Tailored resumes" next="Generate and validate a resume for a job. Built in Phase 4." />} />
        <Route path="applications" element={<Placeholder title="Applications" next="Track what you applied to and which resume you used. Built in Phase 5." />} />
        <Route path="*" element={<Placeholder title="Page not found" next="Use the menu to go back." />} />
      </Route>
    </Routes>
  )
}