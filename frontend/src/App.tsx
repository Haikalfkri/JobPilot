import { Route, Routes } from 'react-router-dom'
import { AppShell } from './layout/AppShell'
import { Placeholder } from './pages/Placeholder'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Placeholder title="Dashboard" next="Job and application activity will appear here." />} />
        <Route path="resume" element={<Placeholder title="Master resume" next="Upload a PDF or DOCX and review the extracted facts. Built in Phase 1." />} />
        <Route path="jobs" element={<Placeholder title="Jobs" next="Discovered listings and match scores. Built in Phases 2 and 3." />} />
        <Route path="tailoring" element={<Placeholder title="Tailored resumes" next="Generate and validate a resume for a job. Built in Phase 4." />} />
        <Route path="applications" element={<Placeholder title="Applications" next="Track what you applied to and which resume you used. Built in Phase 5." />} />
        <Route path="*" element={<Placeholder title="Page not found" next="Use the menu to go back." />} />
      </Route>
    </Routes>
  )
}