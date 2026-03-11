import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import ReportTable from '../components/ReportTable.jsx'

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// QueryBuilder page
// ---------------------------------------------------------------------------
export default function QueryBuilder() {
  const navigate = useNavigate()

  // Ollama
  const [ollamaStatus, setOllamaStatus] = useState(null)
  const [availableModels, setAvailableModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')

  // Requête
  const [prompt, setPrompt] = useState('')
  const [interpreting, setInterpreting] = useState(false)
  const [interpretError, setInterpretError] = useState(null)

  // Résultat
  const [generatedQuery, setGeneratedQuery] = useState(null)
  const [queryJson, setQueryJson] = useState('')  // JSON éditable
  const [jsonError, setJsonError] = useState(null)
  const [result, setResult] = useState(null)
  const [executing, setExecuting] = useState(false)

  // Templates utilisateur
  const [userTemplates, setUserTemplates] = useState([])
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [templateDesc, setTemplateDesc] = useState('')
  const [saving, setSaving] = useState(false)

  const promptRef = useRef(null)
  const abortRef = useRef(null)   // AbortController courant

  // Charger le statut Ollama et les templates au montage
  useEffect(() => {
    apiFetch('/api/query/ollama/status')
      .then(data => {
        setOllamaStatus(data.status)
        setAvailableModels(data.available_models || [])
        setSelectedModel(data.model || '')
      })
      .catch(() => setOllamaStatus('error'))

    loadUserTemplates()
  }, [])

  const loadUserTemplates = () => {
    apiFetch('/api/query/templates')
      .then(data => setUserTemplates(data.templates || []))
      .catch(() => {})
  }

  // ---------------------------------------------------------------------------
  // Annuler l'interprétation en cours
  // ---------------------------------------------------------------------------
  const handleCancel = () => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
  }

  // ---------------------------------------------------------------------------
  // Interprétation Ollama
  // ---------------------------------------------------------------------------
  const handleInterpret = async () => {
    if (!prompt.trim()) return

    // Annuler toute requête précédente
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setInterpreting(true)
    setInterpretError(null)
    setResult(null)
    setGeneratedQuery(null)
    setJsonError(null)

    try {
      const data = await apiFetch('/api/query/interpret', {
        method: 'POST',
        signal: controller.signal,
        body: JSON.stringify({
          request: prompt,
          model: selectedModel || undefined,
          execute: true,
        }),
      })
      setGeneratedQuery(data.query)
      setQueryJson(JSON.stringify(data.query, null, 2))
      if (data.result) setResult(data.result)
      if (data.error) setInterpretError(`Exécution : ${data.error}`)
    } catch (e) {
      if (e.name === 'AbortError') {
        setInterpretError('Interprétation annulée.')
      } else {
        setInterpretError(e.message)
      }
    } finally {
      abortRef.current = null
      setInterpreting(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Ré-exécuter le JSON édité manuellement
  // ---------------------------------------------------------------------------
  const handleExecuteJson = async () => {
    setJsonError(null)
    let query
    try {
      query = JSON.parse(queryJson)
    } catch (e) {
      setJsonError(`JSON invalide : ${e.message}`)
      return
    }
    setExecuting(true)
    try {
      const data = await apiFetch('/api/reports/execute', {
        method: 'POST',
        body: JSON.stringify(query),
      })
      setResult(data)
      setGeneratedQuery(query)
    } catch (e) {
      setJsonError(e.message)
    } finally {
      setExecuting(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Sauvegarde template
  // ---------------------------------------------------------------------------
  const handleSaveTemplate = async () => {
    if (!templateName.trim() || !generatedQuery) return
    setSaving(true)
    try {
      await apiFetch('/api/query/templates', {
        method: 'POST',
        body: JSON.stringify({
          name: templateName,
          description: templateDesc,
          query: JSON.parse(queryJson),
          created_from: prompt,
        }),
      })
      setShowSaveModal(false)
      setTemplateName('')
      setTemplateDesc('')
      loadUserTemplates()
    } catch (e) {
      alert(`Erreur sauvegarde : ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Charger un template utilisateur
  // ---------------------------------------------------------------------------
  const handleLoadTemplate = async (templateId) => {
    try {
      const data = await apiFetch(`/api/query/templates/${templateId}/execute`, {
        method: 'POST',
      })
      const tpl = userTemplates.find(t => t.id === templateId)
      if (tpl) {
        setGeneratedQuery(tpl.query)
        setQueryJson(JSON.stringify(tpl.query, null, 2))
        setPrompt(tpl.created_from || '')
      }
      setResult(data)
    } catch (e) {
      alert(`Erreur : ${e.message}`)
    }
  }

  const handleDeleteTemplate = async (templateId, e) => {
    e.stopPropagation()
    if (!confirm('Supprimer ce template ?')) return
    await fetch(`/api/query/templates/${templateId}`, { method: 'DELETE' })
    loadUserTemplates()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleInterpret()
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="max-w-7xl mx-auto px-6 py-10">

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <button
            onClick={() => navigate('/')}
            className="text-text-muted hover:text-text-primary transition-colors"
          >
            ←
          </button>
          <h1 className="font-display font-extrabold text-3xl text-text-primary">
            Query <span className="gradient-text">Builder</span>
          </h1>
          <OllamaStatusBadge status={ollamaStatus} />
        </div>
        <p className="text-text-secondary text-sm ml-7">
          Décrivez en français ce que vous cherchez — Ollama construit la requête.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Colonne gauche — saisie + templates */}
        <div className="lg:col-span-1 flex flex-col gap-5">

          {/* Saisie Ollama */}
          <div className="rounded-2xl bg-bg-card border border-border p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-display font-semibold text-sm text-text-secondary uppercase tracking-widest">
                Votre demande
              </h2>
              {availableModels.length > 0 && (
                <select
                  value={selectedModel}
                  onChange={e => setSelectedModel(e.target.value)}
                  className="text-xs bg-bg-hover border border-border rounded-lg px-2 py-1
                             text-text-secondary focus:outline-none focus:border-accent-cyan/50"
                >
                  {availableModels.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              )}
            </div>

            <textarea
              ref={promptRef}
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                ollamaStatus === 'ok'
                  ? "Ex: applications critiques avec leur bloc applicatif et RTO inférieur à 4h"
                  : "Ollama non disponible..."
              }
              disabled={ollamaStatus !== 'ok' || interpreting}
              rows={5}
              className="w-full bg-bg-secondary border border-border rounded-xl px-4 py-3
                         text-text-primary text-sm placeholder-text-muted resize-none
                         focus:outline-none focus:border-accent-cyan/50 transition-colors
                         disabled:opacity-40"
            />

            <div className="flex items-center justify-between mt-3">
              <span className="text-xs text-text-muted font-mono">Ctrl+Entrée pour exécuter</span>
              <div className="flex items-center gap-2">
                {interpreting && (
                  <button
                    onClick={handleCancel}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl font-medium text-sm
                               border border-red-500/40 text-red-400
                               hover:bg-red-500/10 transition-colors"
                    title="Annuler l'interprétation"
                  >
                    ✕ Annuler
                  </button>
                )}
                <button
                  onClick={handleInterpret}
                  disabled={!prompt.trim() || ollamaStatus !== 'ok' || interpreting}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl font-medium text-sm
                             bg-gradient-to-r from-accent-cyan to-accent-violet text-white
                             hover:opacity-90 transition-opacity disabled:opacity-40"
                >
                  {interpreting ? (
                    <>
                      <span className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin" />
                      Interprétation…
                    </>
                  ) : (
                    <>✨ Interpréter</>
                  )}
                </button>
              </div>
            </div>

            {interpretError && (
              <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30
                              text-red-400 text-xs font-mono">
                {interpretError}
              </div>
            )}
          </div>

          {/* Templates utilisateur sauvegardés */}
          {userTemplates.length > 0 && (
            <div className="rounded-2xl bg-bg-card border border-border p-5">
              <h2 className="font-display font-semibold text-sm text-text-secondary uppercase tracking-widest mb-3">
                Mes templates
              </h2>
              <div className="flex flex-col gap-2">
                {userTemplates.map(tpl => (
                  <div
                    key={tpl.id}
                    onClick={() => handleLoadTemplate(tpl.id)}
                    className="group flex items-center justify-between p-3 rounded-xl
                               bg-bg-secondary border border-border hover:border-accent-violet/40
                               hover:bg-bg-hover cursor-pointer transition-all"
                  >
                    <div className="min-w-0">
                      <div className="text-sm text-text-primary font-medium truncate">
                        {tpl.name}
                      </div>
                      {tpl.description && (
                        <div className="text-xs text-text-muted truncate">{tpl.description}</div>
                      )}
                      <div className="text-xs font-mono text-text-muted mt-0.5">
                        {tpl.query?.endpoint}
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleDeleteTemplate(tpl.id, e)}
                      className="ml-2 opacity-0 group-hover:opacity-100 text-text-muted
                                 hover:text-red-400 transition-all text-lg leading-none"
                      title="Supprimer"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Colonne droite — JSON généré + résultats */}
        <div className="lg:col-span-2 flex flex-col gap-5">

          {/* JSON généré/éditable */}
          {queryJson && (
            <div className="rounded-2xl bg-bg-card border border-border p-5">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-display font-semibold text-sm text-text-secondary uppercase tracking-widest">
                  Requête générée
                  <span className="ml-2 text-xs font-mono text-accent-cyan normal-case">
                    éditable
                  </span>
                </h2>
                <div className="flex items-center gap-2">
                  {generatedQuery && (
                    <button
                      onClick={() => setShowSaveModal(true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                                 border border-accent-violet/40 text-accent-violet
                                 hover:bg-accent-violet/10 transition-colors"
                    >
                      💾 Sauvegarder
                    </button>
                  )}
                  <button
                    onClick={handleExecuteJson}
                    disabled={executing}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                               bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan
                               hover:bg-accent-cyan/20 transition-colors disabled:opacity-40"
                  >
                    {executing ? '⟳ Exécution…' : '▶ Ré-exécuter'}
                  </button>
                </div>
              </div>

              <textarea
                value={queryJson}
                onChange={e => setQueryJson(e.target.value)}
                rows={12}
                spellCheck={false}
                className="w-full bg-bg-secondary border border-border rounded-xl px-4 py-3
                           text-accent-cyan text-xs font-mono resize-y
                           focus:outline-none focus:border-accent-cyan/50 transition-colors"
              />

              {jsonError && (
                <div className="mt-2 p-2 rounded-lg bg-red-500/10 border border-red-500/30
                                text-red-400 text-xs font-mono">
                  {jsonError}
                </div>
              )}
            </div>
          )}

          {/* Résultats */}
          {result && (
            <div className="rounded-2xl bg-bg-card border border-border p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-display font-semibold text-sm text-text-secondary uppercase tracking-widest">
                  Résultats
                </h2>
                {result.metadata?.title && (
                  <span className="text-sm font-medium text-text-primary">
                    {result.metadata.title}
                  </span>
                )}
              </div>
              <ReportTable result={result} />
            </div>
          )}

          {/* État vide */}
          {!queryJson && !interpreting && (
            <div className="flex flex-col items-center justify-center py-20 text-center
                            rounded-2xl bg-bg-card border border-dashed border-border">
              <div className="text-5xl mb-4">🔮</div>
              <h3 className="font-display font-bold text-lg text-text-primary mb-2">
                Décrivez votre besoin
              </h3>
              <p className="text-text-secondary text-sm max-w-sm">
                Tapez votre demande en français et laissez Ollama construire la requête Mercator.
              </p>
              <div className="mt-4 text-xs font-mono text-text-muted space-y-1">
                <div>"applications avec leur bloc et RTO"</div>
                <div>"serveurs Linux en production"</div>
                <div>"traitements RGPD avec base légale"</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal sauvegarde */}
      {showSaveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md bg-bg-card border border-border rounded-2xl p-6 mx-4">
            <h3 className="font-display font-bold text-xl text-text-primary mb-5">
              Sauvegarder le template
            </h3>

            <div className="flex flex-col gap-4">
              <div>
                <label className="text-xs font-mono text-text-secondary mb-1.5 block">
                  Nom *
                </label>
                <input
                  type="text"
                  value={templateName}
                  onChange={e => setTemplateName(e.target.value)}
                  placeholder="Ex: Applications critiques SAP"
                  autoFocus
                  className="w-full bg-bg-secondary border border-border rounded-xl px-4 py-2.5
                             text-text-primary text-sm focus:outline-none focus:border-accent-cyan/50"
                />
              </div>

              <div>
                <label className="text-xs font-mono text-text-secondary mb-1.5 block">
                  Description
                </label>
                <input
                  type="text"
                  value={templateDesc}
                  onChange={e => setTemplateDesc(e.target.value)}
                  placeholder="Description optionnelle"
                  className="w-full bg-bg-secondary border border-border rounded-xl px-4 py-2.5
                             text-text-primary text-sm focus:outline-none focus:border-accent-cyan/50"
                />
              </div>

              {prompt && (
                <div className="p-3 rounded-xl bg-bg-secondary border border-border">
                  <div className="text-xs font-mono text-text-muted mb-1">Requête originale</div>
                  <div className="text-xs text-text-secondary italic">"{prompt}"</div>
                </div>
              )}
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => { setShowSaveModal(false); setTemplateName(''); setTemplateDesc('') }}
                className="flex-1 px-4 py-2.5 rounded-xl border border-border text-text-secondary
                           hover:text-text-primary hover:border-border-bright text-sm transition-colors"
              >
                Annuler
              </button>
              <button
                onClick={handleSaveTemplate}
                disabled={!templateName.trim() || saving}
                className="flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-accent-cyan
                           to-accent-violet text-white text-sm font-medium
                           hover:opacity-90 transition-opacity disabled:opacity-40"
              >
                {saving ? 'Sauvegarde…' : '💾 Sauvegarder'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Composant statut Ollama
// ---------------------------------------------------------------------------
function OllamaStatusBadge({ status }) {
  if (!status) return null
  const ok = status === 'ok'
  return (
    <span className={`flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-full border ${
      ok
        ? 'bg-accent-green/10 border-accent-green/30 text-accent-green'
        : 'bg-red-500/10 border-red-500/30 text-red-400'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-accent-green animate-pulse' : 'bg-red-500'}`} />
      Ollama {ok ? 'connecté' : 'hors ligne'}
    </span>
  )
}
