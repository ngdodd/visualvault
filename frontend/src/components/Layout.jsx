import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import ThemeSwitcher from './ThemeSwitcher'
import {
  Image,
  Upload,
  Search,
  LogOut,
  User,
  Layers,
  Sparkles,
} from 'lucide-react'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { to: '/', icon: Image, label: 'Gallery' },
    { to: '/upload', icon: Upload, label: 'Upload' },
    { to: '/search', icon: Search, label: 'Search' },
    { to: '/analyze', icon: Sparkles, label: 'Analyze' },
  ]

  return (
    <div className="min-h-screen flex" style={{ backgroundColor: 'var(--color-bg)' }}>
      {/* Sidebar */}
      <aside
        className="w-64 flex flex-col sidebar"
        style={{
          backgroundColor: 'var(--color-bg-secondary)',
          borderRight: 'var(--border-width) solid var(--color-border)',
        }}
      >
        {/* Logo */}
        <div
          className="p-6"
          style={{ borderBottom: 'var(--border-width) solid var(--color-border)' }}
        >
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 flex items-center justify-center"
              style={{
                background: 'linear-gradient(135deg, var(--color-primary), var(--color-primary-hover))',
                borderRadius: 'var(--radius-lg)',
              }}
            >
              <Layers className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg" style={{ color: 'var(--color-text)' }}>VisualVault</h1>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Smart Asset Intelligence</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <ul className="space-y-1">
            {navItems.map(({ to, icon: Icon, label }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-4 py-3 transition-all nav-link ${
                      isActive ? 'nav-link-active' : ''
                    }`
                  }
                  style={({ isActive }) => ({
                    backgroundColor: isActive ? 'var(--color-primary)' : 'transparent',
                    color: isActive ? 'var(--color-primary-text)' : 'var(--color-text-secondary)',
                    borderRadius: 'var(--radius)',
                  })}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* User section */}
        <div
          className="p-4"
          style={{ borderTop: 'var(--border-width) solid var(--color-border)' }}
        >
          <div
            className="flex items-center gap-3 px-4 py-3"
            style={{
              backgroundColor: 'var(--color-bg-tertiary)',
              borderRadius: 'var(--radius)',
            }}
          >
            <div
              className="w-8 h-8 flex items-center justify-center"
              style={{
                backgroundColor: 'var(--color-primary)',
                borderRadius: 'var(--radius-full)',
              }}
            >
              <User className="w-4 h-4" style={{ color: 'var(--color-primary-text)' }} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate" style={{ color: 'var(--color-text)' }}>{user?.email}</p>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Logged in</p>
            </div>
            <ThemeSwitcher compact />
            <button
              onClick={handleLogout}
              className="p-2 rounded-lg transition-colors"
              style={{ color: 'var(--color-text-muted)' }}
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto" style={{ backgroundColor: 'var(--color-bg)' }}>
        <Outlet />
      </main>
    </div>
  )
}
