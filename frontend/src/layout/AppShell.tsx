import { Briefcase, FileText, LayoutDashboard, Radar, Search, Send, Sparkles, Settings } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { HealthIndicator } from '../components/HealthIndicator'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/resume', label: 'Master resume', icon: FileText },
  { to: '/discovery', label: 'Discovery', icon: Radar },
  { to: '/jobs', label: 'Jobs', icon: Search },
  { to: '/tailoring', label: 'Tailored resumes', icon: Sparkles },
  { to: '/applications', label: 'Applications', icon: Send },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function AppShell() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Briefcase size={20} aria-hidden="true" />
          JobPilot
        </div>
        <nav aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className="nav-link">
              <Icon size={18} aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
        <HealthIndicator />
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}