import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/reports.js'
import ReportTable from '../components/ReportTable.jsx'

export default function ReportView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    api.executeTemplate(id)
      .then(setResult)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  return (
    <div className="max-w-7xl mx-auto px-6 py-10">

      {/* Back button */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary
                   mb-8 transition-colors group"
      >
        <svg
          className="w-4 h-4 transition-transform group-hover:-translate-x-0.5"
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
        </svg>
        Retour aux rapports
      </button>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <div className="relative w-12 h-12">
            <div className="absolute inset-0 rounded-full border-2 border-accent-cyan/20" />
            <div className="absolute inset-0 rounded-full border-2 border-transparent
                            border-t-accent-cyan animate-spin" />
          </div>
          <p className="text-text-secondary text-sm font-mono">
            Génération du rapport…
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-6 rounded-xl border border-red-500/30 bg-red-500/10 text-center">
          <div className="text-3xl mb-3">⚠️</div>
          <h3 className="font-display font-bold text-red-400 mb-2">Erreur</h3>
          <p className="text-red-400/80 text-sm font-mono">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="mt-4 px-4 py-2 rounded-lg bg-red-500/20 text-red-400 text-sm
                       hover:bg-red-500/30 transition-colors"
          >
            Retour
          </button>
        </div>
      )}

      {/* Result */}
      {result && !loading && (
        <>
          {/* Header */}
          <div className="mb-8">
            <h1 className="font-display font-extrabold text-3xl text-text-primary mb-2">
              {result.metadata.title || id}
            </h1>
            <div className="flex items-center gap-3 text-xs font-mono text-text-muted">
              <span className="bg-bg-card border border-border px-2 py-0.5 rounded">
                {result.metadata.endpoint}
              </span>
              <span>•</span>
              <span>{result.metadata.total_items} résultats</span>
              <span>•</span>
              <span>
                {new Date(result.metadata.generated_at).toLocaleString('fr-FR')}
              </span>
            </div>
          </div>

          {/* Table */}
          <div>
            <ReportTable result={result} />
          </div>

          {/* Export buttons */}
          <div className="mt-6 flex items-center justify-end gap-3">
            <span className="text-xs text-text-muted font-mono mr-2">Exporter :</span>
            <ExportButton fmt="pdf" label="PDF" icon="📄" templateId={id} />
            <ExportButton fmt="csv" label="CSV" icon="📊" templateId={id} />
            <ExportButton fmt="md"  label="Markdown" icon="📝" templateId={id} />
          </div>
        </>
      )}
    </div>
  )
}

function ExportButton({ fmt, label, icon, templateId }) {
  const [loading, setLoading] = useState(false)

  const handleExport = async () => {
    setLoading(true)
    try {
      const res = await fetch(`/api/reports/templates/${templateId}/export/${fmt}`, {
        method: 'POST',
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const cd = res.headers.get('content-disposition') || ''
      const match = cd.match(/filename="(.+)"/)
      a.download = match ? match[1] : `rapport-${templateId}.${fmt}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert(`Erreur export ${fmt.toUpperCase()} : ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleExport}
      disabled={loading}
      className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border
                 text-text-secondary hover:text-text-primary hover:border-accent-cyan/40
                 hover:bg-accent-cyan/5 text-sm transition-all disabled:opacity-50"
    >
      {loading ? (
        <span className="w-3 h-3 border border-accent-cyan border-t-transparent rounded-full animate-spin" />
      ) : (
        <span>{icon}</span>
      )}
      {label}
    </button>
  )
}