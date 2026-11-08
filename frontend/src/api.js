async function req(method, path, body) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText)
  return res.json()
}

export const api = {
  state: () => req('GET', '/state'),
  start: (phase = 'before') => req('POST', '/scenario/start', { phase }),
  phase: (phase) => req('POST', '/phase', { phase }),
  thread: (phone) => req('GET', `/thread?phone=${encodeURIComponent(phone)}`),
  exposure: () => req('GET', '/exposure'),
  sendActions: () => req('POST', '/before/send_actions'),
  actions: () => req('GET', '/before/actions'),
  recovery: () => req('GET', '/recovery/claims'),
  runAutopay: () => req('POST', '/recovery/run_autopay'),
  autopay: (id) => req('POST', `/claims/${id}/autopay`),
  contractors: () => req('GET', '/contractors'),
  warnScams: () => req('POST', '/recovery/warn_scams'),
  scorecard: () => req('GET', '/scorecard'),
  checkinAll: () => req('POST', '/outreach/checkin_all'),
  inbound: (phone, text) => req('POST', '/dev/inbound', { phone, text }),
  assign: (id, team_id) => req('POST', `/cases/${id}/assign`, { team_id }),
  safe: (id) => req('POST', `/cases/${id}/safe`),
  sweep: (blockId) => req('POST', `/blocks/${blockId}/sweep`),
  claims: () => req('GET', '/claims'),
  messages: (id) => req('GET', `/cases/${id}/messages`),
  advanceClock: (minutes) => req('POST', '/clock/advance', { minutes }),
  shelter: (id) => req('GET', `/shelters/${id}`),
  shelterAccept: (id, case_id) => req('POST', `/shelters/${id}/accept`, { case_id }),
  medGiven: (id, medId) => req('POST', `/shelters/${id}/meds/${medId}/given`),
}

/** Which contract endpoints the backend has so far (teammate builds some of them in parallel). */
export async function detectFeatures() {
  try {
    const spec = await (await fetch('/openapi.json')).json()
    const paths = Object.keys(spec.paths || {})
    return {
      clockAdvance: paths.includes('/api/clock/advance'),
      shelters: paths.some((p) => p.startsWith('/api/shelters')),
    }
  } catch {
    return { clockAdvance: false, shelters: false }
  }
}

export const band = (score) =>
  score >= 70 ? 'Critical' : score >= 40 ? 'High' : score >= 15 ? 'Medium' : 'Low'

export const scoreColor = (score, status) => {
  if (status === 'confirmed_safe') return '#22c55e'
  if (score >= 70) return '#ef4444'
  if (score >= 40) return '#f97316'
  if (score >= 15) return '#eab308'
  if (status === 'self_reported_safe') return '#4ade80'
  return '#64748b'
}

export const SOURCE_LABEL = {
  policyholder: 'Policyholder',
  utility_medical: 'Utility medical list',
  app: 'App user',
  census_estimate: 'Census estimate',
  live: 'Live text',
}

export const STATUS_LABEL = {
  unreached: 'Unreached',
  contacted: 'No reply',
  needs_help: 'Needs help',
  welfare_check: 'Welfare check',
  self_reported_safe: 'Says safe',
  assigned: 'Team assigned',
  confirmed_safe: 'Confirmed safe',
}

export const fmtT = (t) => {
  if (t == null) return '-'
  const sign = t < 0 ? '-' : '+'
  const m = Math.abs(Math.round(t))
  return `T${sign}${Math.floor(m / 60)}h${String(m % 60).padStart(2, '0')}m`
}
