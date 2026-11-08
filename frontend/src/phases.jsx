import { useEffect, useRef, useState } from 'react'
import { CircleMarker, MapContainer, Polygon, Rectangle, TileLayer, Tooltip } from 'react-leaflet'
import { api, assetUrl } from './api'

const CENTER = [29.76, -95.37]
const usd = (n) => (n == null ? '-' : `$${Math.round(n).toLocaleString()}`)
const usdShort = (n) => {
  if (n == null) return '-'
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  if (Math.abs(n) >= 1e3) return `$${Math.round(n / 1e3)}K`
  return `$${Math.round(n)}`
}

/** Poll an endpoint every 2s while mounted. */
function usePoll(fn, deps = []) {
  const [data, setData] = useState(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let alive = true
    const load = () => fn().then((d) => alive && setData(d)).catch(() => {})
    load()
    const id = setInterval(load, 2000)
    return () => { alive = false; clearInterval(id) }
  }, [...deps, tick])
  return [data, () => setTick((t) => t + 1)]
}

const PHASE_INFO = {
  before: { label: 'BEFORE', color: 'bg-amber-500 text-slate-950', goal: 'Prevent losses' },
  during: { label: 'DURING', color: 'bg-sf-red text-white', goal: 'Find everyone, rank by need' },
  after: { label: 'AFTER', color: 'bg-emerald-500 text-slate-950', goal: 'Pay claims fast and fairly' },
}

function untilLandfall(now) {
  if (now < 0) {
    const h = Math.floor(-now / 60)
    return `Landfall in ${h}h`
  }
  if (now < 2880) return `${Math.floor(now / 60)}h since landfall`
  return `Day ${Math.floor(now / 1440)} after landfall`
}

// ---------- banner + scorecard ----------

export function PhaseBanner({ state }) {
  const p = PHASE_INFO[state.event_phase] || PHASE_INFO.before
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-slate-800 bg-slate-900 px-4 py-1.5">
      <span className={`rounded px-2 py-0.5 text-xs font-extrabold tracking-wider ${p.color}`}>{p.label}</span>
      <span className="font-mono text-lg font-bold">{state.clock}</span>
      <span className="text-sm text-slate-300">{untilLandfall(state.now)} · goal: {p.goal}</span>
      <div className="ml-auto"><Scorecard /></div>
    </div>
  )
}

export function Scorecard() {
  const [sc] = usePoll(api.scorecard)
  const [open, setOpen] = useState(false)
  if (!sc) return null
  const Stat = ({ value, label, sub }) => (
    <div className="rounded bg-slate-950 px-2.5 py-1">
      <div className="text-base font-bold leading-tight text-emerald-300">{value}</div>
      <div className="text-[10px] text-slate-400">{label}{sub && <span className="text-slate-500"> · {sub}</span>}</div>
    </div>
  )
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Scorecard</span>
      <Stat value={usdShort(sc.avoided)} label="losses avoided" sub="confirmed actions" />
      <Stat value={sc.cycle_time_days == null ? '-' : `${sc.cycle_time_days} days`} label="claim cycle time"
        sub={`vs ~${sc.cycle_baseline_days} assumed`} />
      <Stat value={sc.cost_per_claim == null ? '-' : usd(sc.cost_per_claim)} label="cost per claim"
        sub={`vs ~${usd(sc.cost_baseline)} assumed`} />
      <div className="text-[10px] leading-tight text-slate-400">
        <div>reached {sc.reached_pct}% · {sc.prepared_high_risk} high-risk prepared</div>
        <div>{usdShort(sc.fraud_held)} held for review</div>
        <button onClick={() => setOpen(true)} className="text-sky-300 underline">How we calculate this</button>
      </div>
      {open && <AssumptionsModal sc={sc} onClose={() => setOpen(false)} />}
    </div>
  )
}

function AssumptionsModal({ sc, onClose }) {
  const a = sc.assumptions
  const rows = [
    ['Car moved to higher ground', usd(sc.avoided_by_type.car), a.car],
    ['Windows shuttered / boarded', usd(sc.avoided_by_type.shutters), a.shutters],
    ['Pre-storm photos on file', usd(sc.avoided_by_type.photos), a.photos],
    ['Medication / evacuation ready', `${sc.prepared_high_risk} people`, a.meds],
  ]
  return (
    <div className="fixed inset-0 z-[3000] grid place-items-center bg-black/60 p-4" onClick={onClose}>
      <div className="max-w-2xl rounded-xl border border-slate-700 bg-slate-900 p-5 text-sm" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-bold">How we calculate this</h2>
          <button onClick={onClose} className="text-slate-400">✕</button>
        </div>
        <p className="mb-3 text-xs text-amber-300">All data is fake. Every rate and baseline below is an <b>assumption</b>;
          real numbers would come from State Farm's own claims data.</p>
        <table className="w-full text-xs">
          <thead className="text-left text-slate-400"><tr><th className="pb-1">Confirmed action</th><th>Avoided</th><th>Assumption</th></tr></thead>
          <tbody>
            {rows.map(([k, v, why]) => (
              <tr key={k} className="border-t border-slate-800 align-top">
                <td className="py-1.5 pr-2 font-semibold">{k}</td><td className="pr-2 text-emerald-300">{v}</td><td className="text-slate-300">{why}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-slate-300">Only <b>confirmed</b> actions count. Unconfirmed actions count $0. We never put a dollar value on people.</p>
        <p className="mt-2 text-xs text-slate-300"><b>Claim cycle time:</b> {a.cycle_time}</p>
        <p className="mt-2 text-xs text-slate-300"><b>Cost per claim:</b> {a.cost_per_claim}</p>
        <p className="mt-2 text-xs text-slate-300"><b>Expected loss:</b> {a.expected_loss}</p>
      </div>
    </div>
  )
}

// ---------- Before ----------

const lossColor = (v) => (v >= 60000 ? '#ef4444' : v >= 25000 ? '#f97316' : v >= 8000 ? '#eab308' : '#64748b')

function BeforeMap({ state, exposure }) {
  return (
    <MapContainer center={[29.752, -95.362]} zoom={14} className="h-full w-full" zoomControl={false} preferCanvas>
      <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" className="dark-tiles" />
      {state.blocks.map((b) => (
        <Rectangle key={b.id} bounds={[[b.bounds[0], b.bounds[1]], [b.bounds[2], b.bounds[3]]]}
          pathOptions={{ color: '#1e3a8a', weight: 0.4, fillColor: '#3b82f6', fillOpacity: b.flood_depth_ft > 0 ? Math.min(0.4, 0.05 + b.flood_depth_ft * 0.05) : 0 }}>
          <Tooltip sticky><div className="text-xs"><b>Block {b.id}</b> · forecast water {b.flood_depth_ft} ft</div></Tooltip>
        </Rectangle>
      ))}
      {exposure && (
        <Polygon positions={exposure.cone} pathOptions={{ color: '#fbbf24', weight: 2, dashArray: '6 6', fillColor: '#fbbf24', fillOpacity: 0.08 }}>
          <Tooltip sticky><div className="text-xs"><b>Forecast cone</b> (fake) · narrows at T−48h and T−24h</div></Tooltip>
        </Polygon>
      )}
      {exposure?.homes.filter((h) => h.policy && !h.demo).map((h) => (
        <CircleMarker key={h.id} center={[h.lat, h.lng]} radius={4}
          pathOptions={{ color: lossColor(h.expected_loss), weight: 1, fillColor: lossColor(h.expected_loss), fillOpacity: 0.8 }}>
          <Tooltip direction="top"><div className="text-xs"><b>{h.name}</b><br />Expected loss {usd(h.expected_loss)} · forecast {h.forecast_depth_ft} ft</div></Tooltip>
        </CircleMarker>
      ))}
      {exposure?.homes.filter((h) => h.demo).map((h) => (
        <CircleMarker key={h.id} center={[h.lat, h.lng]} radius={10}
          pathOptions={{ color: '#ffffff', weight: 3, fillColor: lossColor(h.expected_loss), fillOpacity: 1 }}>
          <Tooltip permanent direction="right"><div className="text-xs"><b>{h.name}</b> · expected loss {usd(h.expected_loss)}</div></Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}

const ACTIONS = [
  ['car', 'Car moved', 'Reply 1'],
  ['shutters', 'Windows shuttered', 'Reply 2'],
  ['meds', 'Meds / evacuation ready', 'Reply 3'],
  ['photos', 'Pre-storm photos', 'Photo'],
]

export function BeforeView({ state, onError }) {
  const [exposure] = usePoll(api.exposure)
  const [actions, reloadActions] = usePoll(api.actions)
  const [busy, setBusy] = useState(false)
  const t = exposure?.totals
  const sent = actions && actions.households > 0
  const send = async () => {
    setBusy(true)
    try { await api.sendActions(); reloadActions() } catch (e) { onError(e.message) } finally { setBusy(false) }
  }
  return (
    <main className="flex min-h-0 flex-1">
      <section className="relative min-w-0 flex-1">
        <BeforeMap state={state} exposure={exposure} />
        <div className="absolute bottom-3 left-3 z-[1000] rounded-lg bg-slate-900/90 p-2 text-[11px] text-slate-300 shadow">
          <div className="mb-1 font-semibold">Expected loss per policy (fake model)</div>
          <div className="flex items-center gap-3">
            {[['#ef4444', '$60K+'], ['#f97316', '$25–60K'], ['#eab308', '$8–25K'], ['#64748b', '< $8K']].map(([c, l]) => (
              <span key={l} className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />{l}</span>
            ))}
          </div>
          <div className="mt-1 text-slate-500">Dashed yellow = forecast cone · blue = forecast flood depth</div>
        </div>
      </section>
      <aside className="scroll-thin flex w-[440px] shrink-0 flex-col gap-3 overflow-y-auto border-l border-slate-800 bg-slate-950 p-3">
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-300">Exposure: in the forecast cone</div>
          {t ? (
            <>
              <div className="grid grid-cols-2 gap-2">
                <Big value={t.policies.toLocaleString()} label="policies in the path" />
                <Big value={usdShort(t.expected_loss)} label="total expected loss" accent="text-red-400" />
                <Big value={usdShort(t.insured_value)} label="insured value (homes + cars)" />
                <Big value={t.vulnerable} label="vulnerable households (oxygen, mobility, 75+)" accent="text-amber-300" />
              </div>
              <div className="mt-2 text-[11px] text-slate-400" title={exposure.formula}>
                <b>Formula</b> (hover): home value × P(damage) × damage share + Σ car value × P(flood)
              </div>
            </>
          ) : <div className="text-sm text-slate-500">Loading…</div>}
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-amber-300">Pre-landfall action texts</span>
            <button disabled={busy || sent} onClick={send}
              className="rounded bg-amber-500 px-3 py-1.5 text-sm font-bold text-slate-950 hover:bg-amber-400 disabled:opacity-40">
              {sent ? `Sent to ${actions.households}` : busy ? 'Sending…' : 'Send action texts'}
            </button>
          </div>
          <p className="mb-2 text-[11px] text-slate-400">Each policyholder in the cone gets 2–4 actions picked from their own data,
            in their language. Sending jumps the clock to T−48h.</p>
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] text-slate-400"><tr><th>Action</th><th>Sent</th><th>Confirmed</th><th /></tr></thead>
            <tbody>
              {ACTIONS.map(([k, label, how]) => {
                const v = actions?.by_type[k] || { sent: 0, confirmed: 0 }
                const pct = v.sent ? Math.round((100 * v.confirmed) / v.sent) : 0
                return (
                  <tr key={k} className="border-t border-slate-800">
                    <td className="py-1.5">{label} <span className="text-[10px] text-slate-500">{how}</span></td>
                    <td>{v.sent}</td>
                    <td className="font-bold text-emerald-300">{v.confirmed}</td>
                    <td className="w-24"><div className="h-1.5 rounded bg-slate-800"><div className="h-1.5 rounded bg-emerald-400" style={{ width: `${pct}%` }} /></div></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <ReyesCard />
      </aside>
    </main>
  )
}

function Big({ value, label, accent }) {
  return (
    <div className="rounded bg-slate-950 px-2 py-1.5">
      <div className={`text-xl font-extrabold ${accent || ''}`}>{value}</div>
      <div className="text-[10px] leading-tight text-slate-400">{label}</div>
    </div>
  )
}

function ReyesCard() {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-3 text-xs text-slate-300">
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Demo household (fictional)</div>
      <b>Ana (34) &amp; Rosa Reyes (71, oxygen)</b> · 1418 Magnolia St · Spanish-preferred · policyholders<br />
      2019 sedan · 22-year-old roof · no shutters · pre-storm photos on file
    </div>
  )
}

// ---------- After ----------

const LANES = [
  ['autopay', 'Auto-pay', 'No human. Paid in hours.', 'border-emerald-600'],
  ['desk', 'Desk adjuster', 'Remote review with photos.', 'border-sky-600'],
  ['field', 'Field adjuster', 'In-person inspection.', 'border-orange-600'],
]

function ClaimCard({ c, onPay }) {
  const [open, setOpen] = useState(c.demo)
  return (
    <div className={`rounded-lg border bg-slate-900 p-2 text-xs ${c.demo ? 'border-white' : 'border-slate-800'}`}>
      <div className="flex cursor-pointer items-start justify-between gap-2" onClick={() => setOpen((v) => !v)}>
        <div>
          <div className="font-semibold text-slate-100">{c.name} {c.demo && <span className="rounded bg-white px-1 text-[9px] font-bold text-slate-900">DEMO</span>}</div>
          <div className="text-slate-400">#{c.claim_number} · {c.damage_label} · filed {c.fnol_when}</div>
        </div>
        <div className="text-right">
          <div className="text-sm font-bold">{usd(c.estimate)}</div>
          {c.paid_t != null ? <span className="rounded bg-emerald-900 px-1.5 text-[10px] font-bold text-emerald-200">PAID {c.paid_when}</span>
            : c.lane === 'autopay' ? <button onClick={(e) => { e.stopPropagation(); onPay(c.id) }}
              className="rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-bold text-white hover:bg-emerald-500">Pay now</button> : null}
        </div>
      </div>
      <div className="mt-1 text-[11px] text-slate-400">{c.lane_reason}</div>
      {c.flags.length > 0 && (
        <div className="mt-1 space-y-0.5">
          {c.flags.map((f) => <div key={f} className="rounded bg-amber-950 px-1.5 py-0.5 text-[10px] text-amber-200">⚑ {f}</div>)}
          <div className="text-[10px] text-slate-500">Flagged for adjuster review. Flags never deny a claim.</div>
        </div>
      )}
      {open && (
        <div className="mt-2 border-t border-slate-800 pt-2">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500">FNOL · {c.fnol.peril}</div>
          <div className="mb-1 text-slate-300">{c.fnol.damage}{c.contractor ? ` · contractor: ${c.contractor}` : ''}</div>
          <div className="flex gap-1.5">
            {c.photos.map((p) => (
              <figure key={p.url + p.label} className="w-1/3">
                <img src={assetUrl(p.url)} alt={p.label} className="w-full rounded border border-slate-700" />
                <figcaption className="text-[9px] text-slate-400">{p.phase === 'pre' ? 'Before' : 'After'}: {p.label}</figcaption>
              </figure>
            ))}
            {!c.has_pre_photos && <div className="w-1/3 self-center text-center text-[10px] text-slate-500">no pre-storm photos on file</div>}
          </div>
          <div className="mt-1 text-[10px] italic text-slate-500">Simulated damage assessment (placeholder images, no vision model).</div>
        </div>
      )}
    </div>
  )
}

export function AfterView({ onError }) {
  const [rec, reload] = usePoll(api.recovery)
  const [ks] = usePoll(api.contractors)
  const [msg, setMsg] = useState(null)
  const act = async (fn, done) => {
    try {
      const r = await fn(); setMsg(done(r)); reload()
      setTimeout(() => setMsg(null), 6000)
    } catch (e) { onError(e.message) }
  }
  if (!rec) return <main className="grid flex-1 place-items-center text-slate-400">Loading claims…</main>
  return (
    <main className="flex min-h-0 flex-1">
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 px-3 py-2 text-xs">
          <span className="text-slate-400">{rec.rule}</span>
          <div className="ml-auto flex gap-2">
            {(() => {
              const unpaid = rec.lanes.autopay.filter((c) => c.paid_t == null).length
              return (
                <button disabled={!unpaid} onClick={() => act(api.runAutopay, (r) => `Auto-paid ${r.paid} claim(s); each person got a text.`)}
                  className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-bold text-white hover:bg-emerald-500 disabled:bg-emerald-900 disabled:text-emerald-300">
                  {unpaid ? `Run auto-pay (${unpaid} ready)` : 'All auto-pay claims paid ✓'}
                </button>
              )
            })()}
            <button onClick={() => act(api.warnScams, (r) => `Scam warning sent to ${r.sent} policyholders in damaged blocks.`)}
              className="rounded border border-slate-600 px-3 py-1.5 text-sm font-semibold hover:bg-slate-800">Send scam warning</button>
          </div>
        </div>
        {msg && <div className="bg-emerald-950 px-3 py-1 text-xs text-emerald-200">{msg}</div>}
        <div className="grid min-h-0 flex-1 grid-cols-3 gap-3 p-3">
          {LANES.map(([id, label, sub, border]) => {
            const list = rec.lanes[id]
            const cap = rec.capacity[id]
            return (
              <div key={id} className={`flex min-h-0 flex-col rounded-lg border-t-4 bg-slate-950 ${border}`}>
                <div className="border-b border-slate-800 p-2">
                  <div className="flex items-baseline justify-between">
                    <span className="text-sm font-bold">{label} <span className="text-slate-400">({list.length})</span></span>
                    <span className="text-xs text-slate-400">{usdShort(list.reduce((s, c) => s + c.estimate, 0))}</span>
                  </div>
                  <div className="text-[11px] text-slate-400">{sub}{cap ? ` · ${cap.adjusters} adjusters (fake) · ${cap.open} open · backlog ${cap.backlog_days} days` : ` · ${list.filter((c) => c.paid_t != null).length} paid`}</div>
                </div>
                <div className="scroll-thin min-h-0 flex-1 space-y-2 overflow-y-auto p-2">
                  {list.map((c) => <ClaimCard key={c.id} c={c} onPay={(cid) => act(() => api.autopay(cid), () => `Paid ${c.claim_number}; ${c.name} got a text.`)} />)}
                </div>
              </div>
            )
          })}
        </div>
      </section>
      <aside className="scroll-thin w-[340px] shrink-0 overflow-y-auto border-l border-slate-800 bg-slate-950 p-3">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-orange-300">Contractors, by fraud flags</div>
        <p className="mb-2 text-[11px] text-slate-400">Rules: shared contractor (≥5 claims, far apart or listed before damage reported), inflated estimate (&gt;1.8× median), assignment of benefits &lt;24h after landfall, not on the (fake) license list.</p>
        <div className="space-y-2">
          {(ks || []).map((k) => (
            <div key={k.id} className={`rounded-lg border p-2 text-xs ${k.flags.length ? 'border-orange-700 bg-orange-950/40' : 'border-slate-800 bg-slate-900'}`}>
              <div className="flex justify-between"><b>{k.name}</b><span>{k.claims.length} claims · {usdShort(k.estimate_total)}</span></div>
              <div className="text-[10px] text-slate-400">{k.licensed ? 'Licensed' : 'Not on license list'} · {k.phone}</div>
              {k.flags.map((f) => <div key={f} className="mt-0.5 text-[11px] text-orange-200">⚑ {f}</div>)}
              {k.flags.length > 0 && <div className="mt-1 text-[10px] text-slate-400">{k.claims.map((c) => c.claim_number).join(', ')}</div>}
            </div>
          ))}
        </div>
      </aside>
    </main>
  )
}

// ---------- phone simulator (the demo family's phone) ----------

const QUICK = {
  before: ['1', 'foto de la casa', '3'],
  during: ['el agua está entrando, mi mamá usa oxígeno'],
  after: [],
}

export function PhoneSim({ open, setOpen, phone, setPhone, text, setText, phase, onSend }) {
  const [thread, setThread] = useState(null)
  const end = useRef(null)
  useEffect(() => {
    if (!open) return
    let alive = true
    const load = () => api.thread(phone).then((d) => alive && setThread(d)).catch(() => {})
    load()
    const id = setInterval(load, 1500)
    return () => { alive = false; clearInterval(id) }
  }, [open, phone])
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }) }, [thread?.messages?.length])
  const right = phase === 'during' ? 'right-[452px]' : 'right-3'
  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className={`fixed bottom-3 ${right} z-[2000] rounded-full bg-slate-800 px-4 py-2 text-sm font-semibold shadow-xl hover:bg-slate-700`}>
        📱 Phone simulator
      </button>
    )
  }
  const send = (t) => { setText(t); onSend(t) }
  return (
    <div className={`fixed bottom-3 ${right} z-[2000] flex h-[460px] w-72 flex-col rounded-[22px] border-4 border-slate-700 bg-slate-950 shadow-2xl`}>
      <div className="flex items-center justify-between border-b border-slate-800 px-3 py-1.5 text-xs">
        <span className="font-semibold">{thread?.household?.name || 'Phone'} <span className="text-slate-500">(rehearsal)</span></span>
        <button onClick={() => setOpen(false)} className="text-slate-500">✕</button>
      </div>
      <input value={phone} onChange={(e) => setPhone(e.target.value)} className="mx-2 mt-1 rounded bg-slate-900 px-2 py-0.5 text-[11px] text-slate-400" />
      <div className="scroll-thin min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2">
        {(thread?.messages || []).map((m) => (
          <div key={m.id} className={`flex ${m.direction === 'in' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] whitespace-pre-line rounded-2xl px-2.5 py-1.5 text-[11px] ${m.direction === 'in' ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-100'}`}>
              {m.body}<div className="mt-0.5 text-[9px] opacity-60">{m.when}</div>
            </div>
          </div>
        ))}
        <div ref={end} />
      </div>
      <div className="flex flex-wrap gap-1 px-2">
        {(QUICK[phase] || []).map((q) => (
          <button key={q} onClick={() => send(q)} className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] hover:bg-slate-700">{q.length > 24 ? q.slice(0, 24) + '…' : q}</button>
        ))}
      </div>
      <form className="flex gap-1 p-2" onSubmit={(e) => { e.preventDefault(); onSend(text) }}>
        <input value={text} onChange={(e) => setText(e.target.value)} className="min-w-0 flex-1 rounded-full bg-slate-800 px-3 py-1 text-xs" />
        <button className="rounded-full bg-sky-600 px-3 text-xs font-bold">↑</button>
      </form>
    </div>
  )
}
