/** ResearchSquid API client */

const BASE = import.meta.env.DEV ? '/api' : ''

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    let detail = ''
    const raw = await res.text().catch(() => '')
    if (raw) {
      try {
        const errorBody = JSON.parse(raw)
        detail = errorBody?.detail || errorBody?.message || JSON.stringify(errorBody)
      } catch {
        detail = raw
      }
    }
    const suffix = detail ? ` - ${detail}` : ''
    throw new Error(`${method} ${path}: ${res.status}${suffix}`)
  }
  return res.json()
}

export const api = {
  startResearch: (config) => request('POST', '/research', config),
  getSession: (id) => request('GET', `/sessions/${id}`),
  getOverview: (id) => request('GET', `/sessions/${id}/overview`),
  getGraph: (id) => request('GET', `/sessions/${id}/graph`),
  getAgents: (id) => request('GET', `/sessions/${id}/agents`),
  getAgentDetail: (sessionId, agentId) =>
    request('GET', `/sessions/${sessionId}/agents/${agentId}`),
  getEvents: (sessionId, limit = 100) =>
    request('GET', `/sessions/${sessionId}/events?limit=${limit}`),
  getReport: (sessionId) => request('GET', `/sessions/${sessionId}/report`),
  searchMemory: (id, query, limit = 10) =>
    request('GET', `/sessions/${id}/memory/search?q=${encodeURIComponent(query)}&limit=${limit}`),
  interviewAgent: (sessionId, data) =>
    request('POST', `/sessions/${sessionId}/interview`, data),
  getFinding: (sessionId, findingId) =>
    request('GET', `/sessions/${sessionId}/findings/${findingId}`),
  getExperiment: (sessionId, experimentId) =>
    request('GET', `/sessions/${sessionId}/experiments/${experimentId}`),
  getCluster: (sessionId, clusterId) =>
    request('GET', `/sessions/${sessionId}/clusters/${clusterId}`),
  getFindings: (sessionId) => request('GET', `/sessions/${sessionId}/findings`),
  getExperiments: (sessionId) => request('GET', `/sessions/${sessionId}/experiments`),

  // Workspace endpoints
  getWorkspaces: (sessionId) =>
    request('GET', `/sessions/${sessionId}/workspaces`),
  listWorkspaceFiles: (sessionId, agentId, path = '') =>
    request('GET', `/sessions/${sessionId}/workspaces/${agentId}/files?path=${encodeURIComponent(path)}`),
  getWorkspaceFile: (sessionId, agentId, filePath) =>
    request('GET', `/sessions/${sessionId}/workspaces/${agentId}/files/${filePath}`),
  getOpenCodeSessions: (sessionId, agentId) =>
    request('GET', `/sessions/${sessionId}/workspaces/${agentId}/opencode`),

  streamUrl: (id) => `${BASE}/sessions/${id}/stream`,

  health: () => request('GET', '/health'),
  continueSession: (sessionId, payload = { additional_budget: 100 }) =>
    request('POST', `/sessions/${sessionId}/continue`, payload),
}
