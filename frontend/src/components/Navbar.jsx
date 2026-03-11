import { Link, useLocation } from 'react-router-dom'

export default function Navbar() {
  const location = useLocation()

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-16 border-b border-border bg-bg-primary/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-cyan to-accent-violet flex items-center justify-center text-sm font-bold text-white shadow-lg shadow-accent-cyan/20">
            M
          </div>
          <span className="font-display font-bold text-lg text-text-primary group-hover:text-accent-cyan transition-colors">
            BI Explorer
          </span>
          <span className="text-xs text-text-muted font-mono bg-bg-card px-2 py-0.5 rounded border border-border">
            Mercator
          </span>
        </Link>

        {/* Nav links */}
        <div className="flex items-center gap-1">
          <NavLink to="/" active={location.pathname === '/'}>
            Tableaux de bord
          </NavLink>
          <NavLink to="/query" active={location.pathname === '/query'}>
            Requête libre
          </NavLink>
        </div>
      </div>
    </nav>
  )
}

function NavLink({ to, active, children }) {
  return (
    <Link
      to={to}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-1 ${
        active
          ? 'bg-accent-cyan/10 text-accent-cyan'
          : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
      }`}
    >
      {children}
    </Link>
  )
}
