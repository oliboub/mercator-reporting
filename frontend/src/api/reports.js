// Les appels /api/* sont proxifiés par nginx → mercator-reporting:8000
// Pas besoin d'URL absolue — fonctionne en dev (proxy Vite) et en prod (proxy nginx)
const API_BASE = ''

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Templates
  getTemplates: () => apiFetch('/api/reports/templates'),

  executeTemplate: (id) =>
    apiFetch(`/api/reports/templates/${id}`, { method: 'POST' }),

  // Requête libre
  executeQuery: (query) =>
    apiFetch('/api/reports/execute', {
      method: 'POST',
      body: JSON.stringify(query),
    }),

  // Santé
  health: () => apiFetch('/health'),
  mercatorHealth: () => apiFetch('/api/mercator/health'),
}