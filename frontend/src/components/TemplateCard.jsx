import { useNavigate } from 'react-router-dom'

const TEMPLATE_META = {
  bia: {
    icon: '⚡',
    color: 'from-amber-500 to-orange-600',
    glow: '#f59e0b',
    tag: 'Continuité',
  },
  ciat: {
    icon: '🛡️',
    color: 'from-cyan-400 to-blue-600',
    glow: '#00d4ff',
    tag: 'Sécurité',
  },
  rgpd: {
    icon: '🔐',
    color: 'from-violet-500 to-purple-700',
    glow: '#7c3aed',
    tag: 'Conformité',
  },
  'inventaire-applicatif': {
    icon: '📦',
    color: 'from-emerald-400 to-teal-600',
    glow: '#10b981',
    tag: 'Inventaire',
  },
  'inventaire-serveurs': {
    icon: '🖥️',
    color: 'from-pink-500 to-rose-600',
    glow: '#e879f9',
    tag: 'Infrastructure',
  },
}

export default function TemplateCard({ template, index }) {
  const navigate = useNavigate()
  const meta = TEMPLATE_META[template.id] || {
    icon: '📊',
    color: 'from-gray-500 to-gray-700',
    glow: '#888',
    tag: 'Rapport',
  }

  return (
    <button
      onClick={() => navigate(`/templates/${template.id}`)}
      className="group relative w-full text-left rounded-2xl bg-bg-card border border-border
                 transition-all duration-300 hover:border-transparent hover:scale-[1.02]
                 overflow-hidden focus:outline-none focus:ring-2 focus:ring-accent-cyan/50"
      style={{
        animationDelay: `${index * 80}ms`,
      }}
    >
      {/* Glow hover effect */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-2xl"
        style={{
          background: `radial-gradient(ellipse at top left, ${meta.glow}18 0%, transparent 60%)`,
        }}
      />

      {/* Border gradient on hover */}
      <div
        className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"
        style={{
          padding: '1px',
          background: `linear-gradient(135deg, ${meta.glow}66, transparent 60%)`,
          WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
          WebkitMaskComposite: 'xor',
          maskComposite: 'exclude',
        }}
      />

      <div className="relative p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          {/* Icon */}
          <div
            className={`w-12 h-12 rounded-xl bg-gradient-to-br ${meta.color} flex items-center
                        justify-center text-2xl shadow-lg transition-transform duration-300
                        group-hover:scale-110 group-hover:rotate-3`}
            style={{ boxShadow: `0 8px 24px ${meta.glow}33` }}
          >
            {meta.icon}
          </div>

          {/* Tag */}
          <span
            className="text-xs font-mono font-medium px-2.5 py-1 rounded-full border"
            style={{
              color: meta.glow,
              borderColor: `${meta.glow}44`,
              backgroundColor: `${meta.glow}11`,
            }}
          >
            {meta.tag}
          </span>
        </div>

        {/* Title */}
        <h3 className="font-display font-bold text-lg text-text-primary mb-2 leading-tight
                       group-hover:text-white transition-colors">
          {template.title}
        </h3>

        {/* Description */}
        <p className="text-sm text-text-secondary leading-relaxed mb-5">
          {template.description}
        </p>

        {/* Footer */}
        <div className="flex items-center justify-between pt-4 border-t border-border">
          <span className="text-xs font-mono text-text-muted">
            {template.endpoint}
          </span>
          <div
            className="flex items-center gap-1.5 text-xs font-medium transition-all duration-200
                       group-hover:gap-2.5"
            style={{ color: meta.glow }}
          >
            Générer
            <svg
              className="w-3.5 h-3.5 transition-transform duration-200 group-hover:translate-x-0.5"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>
          </div>
        </div>
      </div>
    </button>
  )
}