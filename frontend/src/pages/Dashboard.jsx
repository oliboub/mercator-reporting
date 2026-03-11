import { useEffect, useState } from 'react'
import { api } from '../api/reports.js'
import TemplateCard from '../components/TemplateCard.jsx'

export default function Dashboard() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [apiStatus, setApiStatus] = useState(null)

  useEffect(() => {
    Promise.all([api.getTemplates(), api.mercatorHealth()])
      .then(([tplData, healthData]) => {
        setTemplates(tplData.templates)
        setApiStatus(healthData.status)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-7xl mx-auto px-6 py-10">

      {/* Hero */}
      <div className="mb-12 relative">
        {/* Background decoration */}
        <div className="absolute -top-10 -left-10 w-64 h-64 rounded-full opacity-5
                        bg-gradient-to-br from-accent-cyan to-accent-violet blur-3xl pointer-events-none" />

        <div
          className="inline-flex items-center gap-2 text-xs font-mono text-accent-cyan
                     bg-accent-cyan/10 border border-accent-cyan/30 rounded-full px-3 py-1 mb-4"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-pulse-slow" />
          Mercator CMDB
        </div>

        <h1 className="font-display font-extrabold text-4xl md:text-5xl text-text-primary mb-3 leading-tight">
          BI{' '}
          <span className="gradient-text">Explorer</span>
        </h1>

        <p className="text-text-secondary text-lg max-w-xl">
          Générez vos rapports Mercator en un clic — BIA, CIAT, RGPD et inventaires.
        </p>

        {/* API Status */}
        {!loading && (
          <div className="mt-4 flex items-center gap-2 text-xs font-mono">
            <span
              className={`w-2 h-2 rounded-full ${apiStatus === 'ok' ? 'bg-accent-green animate-pulse-slow' : 'bg-red-500'}`}
            />
            <span className="text-text-muted">
              Mercator :{' '}
              <span className={apiStatus === 'ok' ? 'text-accent-green' : 'text-red-400'}>
                {apiStatus === 'ok' ? 'connecté' : 'hors ligne'}
              </span>
            </span>
          </div>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-8 p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 text-sm font-mono">
          ⚠ Erreur de connexion à l'API : {error}
        </div>
      )}

      {/* Loading skeletons */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="h-52 rounded-2xl shimmer-bg border border-border"
            />
          ))}
        </div>
      )}

      {/* Templates grid */}
      {!loading && templates.length > 0 && (
        <>
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-display font-semibold text-sm text-text-secondary uppercase tracking-widest">
              Rapports disponibles
            </h2>
            <span className="text-xs font-mono text-text-muted">
              {templates.length} templates
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {templates.map((tpl, i) => (
              <TemplateCard key={tpl.id} template={tpl} index={i} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}